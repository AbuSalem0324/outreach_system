#!/usr/bin/env python3
"""Deterministic lead discovery: find.md stages 0–4.

No LLM. No writes to contacts. places_seen is the only table touched.
Stage 5 (AI) and Stage 6 (contacts insert) are out of scope.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ENV_PATHS = (
    Path("/root/.hermes/.env"),
    Path("/root/hermes/.env"),
)
SKILLSET_FILES = {
    "icp": Path("/tmp/outreach_icp-definitions.md"),
    "find": Path("/tmp/outreach_find.md"),
}
ICP_SOURCE_URL = "https://raw.githubusercontent.com/AbuSalem0324/outreach_system/master/icp-definitions.md"
PLACES_SEARCH = "https://places.googleapis.com/v1/places:searchText"
CH_BASE = "https://api.company-information.service.gov.uk"
USER_AGENT = "DataBardFind/0.1 (+https://databard.xyz)"
PAGE_TOKEN_WAIT_S = 2.2
HTTP_TIMEOUT_S = 20
SCRAPE_TIMEOUT_S = 12
CUTOFF = 40

CATEGORY_QUERY_TERMS = {
    "food_drink_manufacturing": "food manufacturer",
    "fmcg_wholesale_distribution": "wholesale food distributor",
    "logistics": "warehousing and storage",
    "light_engineering": "engineering manufacturer",
    "professional_services": "professional services firm",
}

SITE_KEYWORDS = (
    "manual reporting",
    "spreadsheet",
    "spreadsheets",
    "excel",
    "forecast",
    "forecasting",
    "stock control",
    "inventory",
    "stocktake",
    "demand planning",
    "production planning",
    "order management",
    "warehouse",
    "wms",
    "erp",
)

BI_SIGNATURES = (
    "powerbi",
    "power-bi",
    "power bi",
    "tableau",
    "lookerstudio",
    "looker studio",
    "looker.com",
    "datastudio",
    "qlik",
    "sisense",
)

INTEREST_PATHS = ("about", "contact", "team", "careers", "people", "our-story", "who-we-are")
MAILTO_RE = re.compile(r"mailto:([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
POSTCODE_RE = re.compile(
    r"\b(?:GIR\s*0AA|[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b",
    re.I,
)
ACCOUNTS_RANK = {"micro": 0, "micro-entity": 0, "small": 1, "medium": 2}

SSL_CTX = ssl.create_default_context()


def log(msg: str, **fields: Any) -> None:
    if fields:
        extras = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items())
        print(f"{msg} {extras}", flush=True)
    else:
        print(msg, flush=True)


def _fmt(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip("'").strip('"')


def places_key() -> str:
    return os.environ.get("GOOGLE_PLACES_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def ch_key() -> str:
    for name in ("COMPANY_HOUSE", "COMPANIES_HOUSE_API_KEY", "COMPANIES_HOUSE_KEY", "CH_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    return ""


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = HTTP_TIMEOUT_S,
) -> tuple[int, Any]:
    body = None
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            raw = resp.read()
            data = json.loads(raw.decode("utf-8")) if raw else None
            return resp.status, data
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            data = {"error": raw.decode("utf-8", errors="replace")[:400]}
        return exc.code, data


def http_text(url: str, *, timeout: int = SCRAPE_TIMEOUT_S, max_bytes: int = 400_000) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            final = resp.geturl()
            raw = resp.read(max_bytes)
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype.lower() and not raw[:32].lstrip().lower().startswith((b"<!doctype", b"<html")):
                return resp.status, final, ""
            return resp.status, final, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, url, ""
    except Exception:
        return 0, url, ""


# ---------------------------------------------------------------------------
# ICP
# ---------------------------------------------------------------------------


def fetch_icp_markdown() -> str:
    req = urllib.request.Request(ICP_SOURCE_URL, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S, context=SSL_CTX) as resp:
        return resp.read().decode("utf-8")


def parse_active_icp(markdown: str) -> dict[str, Any]:
    if yaml is None:
        raise SystemExit("PyYAML required to parse icp-definitions.md")
    blocks = re.findall(r"```yaml\n(.*?)```", markdown, re.S)
    active = None
    for block in blocks:
        doc = yaml.safe_load(block)
        if isinstance(doc, dict) and doc.get("active") is True:
            active = doc
            break
    if not active:
        raise SystemExit("no active: true ICP found in icp-definitions.md")
    return active


def flatten_sic(icp: dict[str, Any]) -> dict[str, list[str]]:
    raw = icp.get("sic_codes") or {}
    if not isinstance(raw, dict):
        return {"all": [str(x) for x in raw]}
    return {str(cat): [str(c) for c in codes] for cat, codes in raw.items()}


def size_exclude(icp: dict[str, Any]) -> list[str]:
    band = (icp.get("company_size_band") or {}).get("companies_house_accounts_type_exclude") or []
    return [str(x).lower() for x in band]


def norm_sic(code: str) -> str:
    return re.sub(r"\D", "", code)


def sic_intersects(ch_codes: list[str], icp_codes: list[str]) -> list[str]:
    hits = []
    icp_n = [norm_sic(c) for c in icp_codes if norm_sic(c)]
    for raw in ch_codes:
        n = norm_sic(raw)
        if not n:
            continue
        for icp_c in icp_n:
            if n.startswith(icp_c) or icp_c.startswith(n):
                hits.append(raw)
                break
    return hits


def category_for_sic(sic: str, by_cat: dict[str, list[str]]) -> str | None:
    n = norm_sic(sic)
    for cat, codes in by_cat.items():
        for c in codes:
            cn = norm_sic(c)
            if n.startswith(cn) or cn.startswith(n):
                return cat
    return None


# ---------------------------------------------------------------------------
# Supabase / places_seen
# ---------------------------------------------------------------------------


class Supabase:
    def __init__(self, url: str, key: str) -> None:
        self.base = url.rstrip("/")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def seen_for_icp(self, icp_id: str) -> list[dict[str, Any]]:
        qs = urllib.parse.urlencode({"icp_id": f"eq.{icp_id}", "select": "place_id,domain,outcome"})
        status, data = http_json(f"{self.base}/rest/v1/places_seen?{qs}", headers=self.headers)
        if status >= 300:
            raise RuntimeError(f"places_seen list failed HTTP {status}: {data}")
        return data or []

    def upsert(self, row: dict[str, Any]) -> dict[str, Any]:
        headers = dict(self.headers)
        headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "place_id": row["place_id"],
            "domain": row.get("domain"),
            "icp_id": row.get("icp_id"),
            "outcome": row["outcome"],
            "last_checked_at": now,
        }
        status, data = http_json(
            f"{self.base}/rest/v1/places_seen?on_conflict=place_id",
            method="POST",
            payload=payload,
            headers=headers,
        )
        if status >= 300:
            raise RuntimeError(f"places_seen upsert failed HTTP {status}: {data}")
        return (data[0] if isinstance(data, list) and data else data) or payload


# ---------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------


def places_text_search(query: str, page_token: str | None = None, page_size: int = 20) -> dict[str, Any]:
    payload: dict[str, Any] = {"textQuery": query, "pageSize": page_size}
    if page_token:
        payload["pageToken"] = page_token
    status, data = http_json(
        PLACES_SEARCH,
        method="POST",
        payload=payload,
        headers={
            "X-Goog-Api-Key": places_key(),
            "X-Goog-FieldMask": "places.id,places.websiteUri,nextPageToken",
        },
    )
    if status >= 300:
        raise RuntimeError(f"Places search HTTP {status}: {data}")
    return data or {}


def domain_from_website(website: str | None) -> str | None:
    if not website:
        return None
    parsed = urlparse(website if "://" in website else f"https://{website}")
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    host = host.split(":")[0].strip("/")
    return host or None


# ---------------------------------------------------------------------------
# HTML scrape
# ---------------------------------------------------------------------------


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self._in_title = False
        self.og_site_name: str | None = None
        self.og_title: str | None = None
        self.links: list[str] = []
        self.mailtos: list[str] = []
        self.text_parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript"}:
            self._skip = True
        if tag == "meta":
            prop = (ad.get("property") or ad.get("name") or "").lower()
            content = ad.get("content") or ""
            if prop == "og:site_name" and content:
                self.og_site_name = content.strip()
            if prop == "og:title" and content:
                self.og_title = content.strip()
        if tag == "a":
            href = ad.get("href") or ""
            if href.lower().startswith("mailto:"):
                self.mailtos.append(href)
            elif href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)


def parse_html(html: str) -> PageParser:
    parser = PageParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser


def display_name_from_html(html: str) -> str | None:
    p = parse_html(html)
    for cand in (p.og_site_name, p.og_title, "".join(p.title_parts).strip()):
        if cand and cand.strip():
            name = re.split(r"\s+[|\-–—:]\s+", cand.strip())[0].strip()
            if name:
                return name[:200]
    return None


def collect_site(homepage: str) -> dict[str, Any]:
    status, final_url, html = http_text(homepage)
    pages = [{"url": final_url, "status": status, "html": html}]
    if not html:
        return {
            "homepage_status": status,
            "final_url": final_url,
            "company_name": None,
            "emails": [],
            "has_team_page": False,
            "has_careers_page": False,
            "keyword_hits": [],
            "bi_signatures": [],
            "postcode": None,
            "pages_fetched": 1,
        }

    p0 = parse_html(html)
    extra_urls: list[str] = []
    for href in p0.links:
        low = href.lower()
        if any(token in low for token in INTEREST_PATHS):
            extra_urls.append(urljoin(final_url, href))
    seen = {final_url}
    for url in extra_urls:
        if url in seen or len(pages) >= 5:
            continue
        seen.add(url)
        st, fu, hx = http_text(url)
        pages.append({"url": fu, "status": st, "html": hx})

    combined_html = "\n".join(p["html"] for p in pages if p["html"])
    combined_text = " ".join(
        " ".join(parse_html(p["html"]).text_parts) for p in pages if p["html"]
    )
    low_html = combined_html.lower()
    low_text = combined_text.lower()

    emails = []
    for blob in (combined_html,):
        emails.extend(MAILTO_RE.findall(blob))
        emails.extend(EMAIL_RE.findall(blob))
    clean_emails = []
    junk_suffix = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".woff")
    for e in emails:
        e = e.lower().rstrip(".,;)")
        if e.endswith(junk_suffix):
            continue
        if any(x in e for x in ("example.com", "domain.com", "sentry.io", "wixpress", "cloudflare", "schema.org")):
            continue
        if e not in clean_emails:
            clean_emails.append(e)

    keyword_hits = [k for k in SITE_KEYWORDS if k in low_text]
    bi = [s for s in BI_SIGNATURES if s in low_html]
    has_team = any("team" in (p["url"] or "").lower() or "people" in (p["url"] or "").lower() for p in pages)
    has_careers = any("career" in (p["url"] or "").lower() or "jobs" in (p["url"] or "").lower() for p in pages)
    pc = POSTCODE_RE.search(combined_text)

    return {
        "homepage_status": status,
        "final_url": final_url,
        "company_name": display_name_from_html(html),
        "emails": clean_emails[:8],
        "has_team_page": has_team,
        "has_careers_page": has_careers,
        "keyword_hits": keyword_hits,
        "bi_signatures": sorted(set(bi)),
        "postcode": pc.group(0).upper() if pc else None,
        "pages_fetched": len(pages),
    }


# ---------------------------------------------------------------------------
# Companies House
# ---------------------------------------------------------------------------


class CompaniesHouse:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        token = __import__("base64").b64encode(f"{api_key}:".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Accept": "application/json", "User-Agent": USER_AGENT}
        self.ok = True
        self.auth_error: str | None = None

    def _get(self, path: str, params: dict[str, Any] | None = None) -> tuple[int, Any]:
        if not self.ok:
            return 401, {"error": self.auth_error}
        url = CH_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        status, data = http_json(url, headers=self.headers)
        if status == 401 and self.ok:
            self.ok = False
            self.auth_error = "Companies House 401 Invalid Authorization — check COMPANY_HOUSE"
            log("stage2=ch_auth_failed", error=self.auth_error)
        return status, data

    def search(self, q: str) -> list[dict[str, Any]]:
        q = (q or "").strip()
        if not q:
            return []
        status, data = self._get("/search/companies", {"q": q, "items_per_page": 5})
        if status >= 300:
            log("stage2=ch_search_error", q=q, http=status)
            return []
        return list((data or {}).get("items") or [])

    def profile(self, company_number: str) -> dict[str, Any] | None:
        status, data = self._get(f"/company/{urllib.parse.quote(company_number)}")
        if status >= 300:
            log("stage2=ch_profile_error", company_number=company_number, http=status)
            return None
        return data

    def charges_count(self, company_number: str) -> int | None:
        status, data = self._get(f"/company/{urllib.parse.quote(company_number)}/charges")
        if status == 404:
            return 0
        if status >= 300:
            return None
        return (data or {}).get("total_count")

    def filing_trend(self, company_number: str) -> dict[str, Any]:
        status, data = self._get(
            f"/company/{urllib.parse.quote(company_number)}/filing-history",
            {"category": "accounts", "items_per_page": 25},
        )
        if status >= 300:
            return {"types": [], "trend": None}
        items = (data or {}).get("items") or []
        types: list[str] = []
        for item in reversed(items):  # oldest first
            desc = (item.get("description") or "").lower()
            for label in ("micro-entity", "micro", "small", "medium", "full"):
                if f"accounts-type-{label}" in desc or f"accounts_type_{label}" in desc or f"type-{label}" in desc:
                    types.append("micro-entity" if label == "micro" else label)
                    break
        trend = None
        ranks = [ACCOUNTS_RANK[t] for t in types if t in ACCOUNTS_RANK]
        if len(ranks) >= 2 and ranks[-1] > ranks[0]:
            trend = f"{types[0]}->{types[-1]}"
        return {"types": types[-6:], "trend": trend}


def pick_ch_match(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    active = [i for i in items if (i.get("company_status") or "").lower() == "active"]
    pool = active or items
    return pool[0]


def accounts_type_from_profile(profile: dict[str, Any]) -> str | None:
    last = ((profile.get("accounts") or {}).get("last_accounts") or {})
    t = last.get("type")
    if isinstance(t, str) and t.strip():
        return t.strip().lower()
    return None


def accounts_excluded(acc_type: str | None, exclude: list[str]) -> bool:
    """True only when CH filing regime is an explicit exclude (micro/dormant)."""
    if not acc_type:
        return False
    mapped = acc_type
    if acc_type in {"micro-entity", "micro"}:
        mapped = "micro-entity"
    return mapped in {e.lower() for e in exclude}


# ---------------------------------------------------------------------------
# Stage 4 score
# ---------------------------------------------------------------------------


def score_candidate(
    *,
    query_category: str,
    sic_hits: list[str],
    sic_category: str | None,
    acc_type: str | None,
    acc_fit: bool | None,
    scrape: dict[str, Any],
    filing_trend: str | None,
) -> tuple[int, dict[str, int]]:
    parts: dict[str, int] = {}
    if sic_hits and sic_category == query_category:
        parts["sic"] = 30
    elif sic_hits:
        parts["sic"] = 15
    else:
        parts["sic"] = 0

    # Accounts type is Stage 2 pass/fail only. Do not rank within it.

    kw = min(20, 5 * len(scrape.get("keyword_hits") or []))
    parts["keywords"] = kw
    parts["team"] = 8 if scrape.get("has_team_page") else 0
    parts["careers"] = 8 if scrape.get("has_careers_page") else 0
    parts["no_bi"] = 0 if scrape.get("bi_signatures") else 10
    if filing_trend in {"micro->small", "micro-entity->small", "small->medium"}:
        parts["filing_trend"] = 8
    else:
        parts["filing_trend"] = 0
    return sum(parts.values()), parts


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@dataclass
class Survivor:
    place_id: str
    domain: str | None
    website: str | None
    company_name: str | None
    icp_id: str
    query: str
    query_category: str
    score: int
    score_parts: dict[str, int]
    ch: dict[str, Any] | None
    scrape: dict[str, Any]


def process_place(
    *,
    place_id: str,
    website: str | None,
    icp: dict[str, Any],
    query: str,
    query_category: str,
    db: Supabase,
    ch: CompaniesHouse,
    seen_skip: set[str],
    domain_skip: set[str],
) -> Survivor | None:
    icp_id = icp["icp_id"]
    by_cat = flatten_sic(icp)
    all_sic = [c for codes in by_cat.values() for c in codes]
    exclude = size_exclude(icp)
    domain = domain_from_website(website)

    if place_id in seen_skip:
        log("stage0=skip", place_id=place_id, reason="already_evaluated")
        return None
    if domain and domain in domain_skip:
        log("stage0=skip", place_id=place_id, domain=domain, reason="domain_already_evaluated")
        return None

    if not website or not domain:
        db.upsert({"place_id": place_id, "domain": domain, "icp_id": icp_id, "outcome": "rejected_no_website"})
        log("stage1=reject", place_id=place_id, outcome="rejected_no_website")
        return None

    db.upsert({"place_id": place_id, "domain": domain, "icp_id": icp_id, "outcome": "pending"})
    log("stage1=website", place_id=place_id, domain=domain)

    scrape = collect_site(website)
    name = scrape.get("company_name")
    log(
        "stage3=scrape",
        place_id=place_id,
        company_name=name or "-",
        emails=",".join(scrape.get("emails") or []) or "-",
        team=scrape.get("has_team_page"),
        careers=scrape.get("has_careers_page"),
        keywords=",".join(scrape.get("keyword_hits") or []) or "-",
        bi=",".join(scrape.get("bi_signatures") or []) or "-",
        http=scrape.get("homepage_status"),
    )

    ch_data: dict[str, Any] | None = None
    sic_hits: list[str] = []
    sic_cat: str | None = None
    acc_type: str | None = None
    excluded = False
    filing_trend: str | None = None

    search_q = name or ""
    items = ch.search(search_q) if search_q else []
    if not items and scrape.get("postcode"):
        items = ch.search(scrape["postcode"])
        if items:
            log("stage2=ch_via_postcode", place_id=place_id, postcode=scrape["postcode"])
    match = pick_ch_match(items)
    if not match:
        log("stage2=no_ch_match", place_id=place_id, searched=search_q or "-", note="carry_to_stage3")
    else:
        number = match.get("company_number")
        profile = ch.profile(number) if number else None
        if not profile:
            log("stage2=no_ch_profile", place_id=place_id, company_number=number)
        else:
            status = (profile.get("company_status") or "").lower()
            acc_type = accounts_type_from_profile(profile)
            excluded = accounts_excluded(acc_type, exclude)
            ch_sics = [str(s) for s in (profile.get("sic_codes") or [])]
            sic_hits = sic_intersects(ch_sics, all_sic)
            if sic_hits:
                sic_cat = category_for_sic(sic_hits[0], by_cat)
            charges = ch.charges_count(number) if number else None
            trend = ch.filing_trend(number) if number else {"types": [], "trend": None}
            filing_trend = trend.get("trend")
            ch_data = {
                "company_number": number,
                "company_name": profile.get("company_name"),
                "company_status": status,
                "accounts_type": acc_type,
                "sic_codes": ch_sics,
                "sic_hits": sic_hits,
                "charges_count": charges,
                "filing_trend": filing_trend,
                "filing_types": trend.get("types"),
            }
            log(
                "stage2=ch",
                place_id=place_id,
                company_number=number,
                status=status,
                accounts_type=acc_type or "-",
                sic_hits=",".join(sic_hits) or "-",
                charges=charges,
                trend=filing_trend or "-",
            )
            if status != "active":
                db.upsert({"place_id": place_id, "domain": domain, "icp_id": icp_id, "outcome": "rejected_status"})
                log("stage2=reject", place_id=place_id, outcome="rejected_status", status=status)
                return None
            if excluded:
                db.upsert({"place_id": place_id, "domain": domain, "icp_id": icp_id, "outcome": "rejected_size"})
                log("stage2=reject", place_id=place_id, outcome="rejected_size", accounts_type=acc_type)
                return None
            if ch_sics and not sic_hits:
                db.upsert({"place_id": place_id, "domain": domain, "icp_id": icp_id, "outcome": "rejected_sic"})
                log("stage2=reject", place_id=place_id, outcome="rejected_sic", sic=",".join(ch_sics))
                return None

    total, parts = score_candidate(
        query_category=query_category,
        sic_hits=sic_hits,
        sic_category=sic_cat,
        acc_type=acc_type,
        acc_fit=None,
        scrape=scrape,
        filing_trend=filing_trend,
    )
    log("stage4=score", place_id=place_id, score=total, cutoff=CUTOFF, parts=parts)
    if total < CUTOFF:
        db.upsert({"place_id": place_id, "domain": domain, "icp_id": icp_id, "outcome": "rejected_score"})
        log("stage4=reject", place_id=place_id, outcome="rejected_score", score=total)
        return None

    db.upsert({"place_id": place_id, "domain": domain, "icp_id": icp_id, "outcome": "passed_to_ai"})
    log("stage4=pass", place_id=place_id, outcome="passed_to_ai", score=total)
    return Survivor(
        place_id=place_id,
        domain=domain,
        website=website,
        company_name=name or (ch_data or {}).get("company_name"),
        icp_id=icp_id,
        query=query,
        query_category=query_category,
        score=total,
        score_parts=parts,
        ch=ch_data,
        scrape={k: v for k, v in scrape.items() if k != "html"},
    )


def run(args: argparse.Namespace) -> int:
    for path in ENV_PATHS:
        load_env(path)
    if not places_key():
        raise SystemExit("missing Places key (GOOGLE_PLACES_KEY / GOOGLE_API_KEY)")
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SECRET_KEY"):
        raise SystemExit("missing SUPABASE_URL / SUPABASE_SECRET_KEY")

    log("find=start", icp_source=ICP_SOURCE_URL)
    icp = parse_active_icp(fetch_icp_markdown())
    icp_id = icp["icp_id"]
    by_cat = flatten_sic(icp)
    regions = list((icp.get("geography") or {}).get("primary") or [])
    if args.category:
        if args.category not in by_cat:
            raise SystemExit(f"unknown category {args.category}; have {list(by_cat)}")
        by_cat = {args.category: by_cat[args.category]}
    if args.region:
        regions = [args.region]
    log(
        "icp=active",
        icp_id=icp_id,
        categories=",".join(by_cat),
        regions=",".join(regions),
        size_exclude=",".join(size_exclude(icp)),
    )

    db = Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    ch = CompaniesHouse(ch_key())
    existing = db.seen_for_icp(icp_id)
    seen_skip = {r["place_id"] for r in existing if r.get("outcome") and r["outcome"] != "pending"}
    domain_skip = {
        r["domain"]
        for r in existing
        if r.get("domain") and r.get("outcome") and r["outcome"] != "pending"
    }
    log("stage0=loaded", skip_place_ids=len(seen_skip), skip_domains=len(domain_skip), pending=sum(1 for r in existing if r.get("outcome") == "pending"))

    survivors: list[Survivor] = []
    processed = 0
    queries: list[tuple[str, str, str]] = []
    for cat, _codes in by_cat.items():
        term = CATEGORY_QUERY_TERMS.get(cat, cat.replace("_", " "))
        for region in regions:
            queries.append((cat, region, f"{term} {region}"))

    for cat, region, query in queries:
        if args.limit is not None and processed >= args.limit:
            break
        log("stage1=query", category=cat, region=region, query=query)
        page_token = None
        pages = 0
        while True:
            if args.limit is not None and processed >= args.limit:
                break
            if args.max_pages is not None and pages >= args.max_pages:
                break
            if page_token:
                time.sleep(PAGE_TOKEN_WAIT_S)
            data = places_text_search(query, page_token=page_token)
            pages += 1
            results = data.get("places") or []
            log("stage1=page", query=query, page=pages, n=len(results))
            for place in results:
                if args.limit is not None and processed >= args.limit:
                    break
                pid = place.get("id")
                if not pid:
                    continue
                website = place.get("websiteUri")
                processed += 1
                try:
                    survivor = process_place(
                        place_id=pid,
                        website=website,
                        icp=icp,
                        query=query,
                        query_category=cat,
                        db=db,
                        ch=ch,
                        seen_skip=seen_skip,
                        domain_skip=domain_skip,
                    )
                except Exception as exc:
                    log("error=process", place_id=pid, error=exc)
                    continue
                if survivor:
                    survivors.append(survivor)
                    seen_skip.add(pid)
                    if survivor.domain:
                        domain_skip.add(survivor.domain)
                elif pid:
                    seen_skip.add(pid)
            page_token = data.get("nextPageToken")
            if not page_token:
                break

    print("\n===== passed_to_ai =====", flush=True)
    print(json.dumps([asdict(s) for s in survivors], indent=2), flush=True)
    log("find=done", processed=processed, passed=len(survivors), cutoff=CUTOFF)
    return 0


def main() -> int:
    global CUTOFF
    p = argparse.ArgumentParser(description="find.md stages 0–4 (deterministic)")
    p.add_argument("--limit", type=int, default=8, help="max new Places results to process")
    p.add_argument("--max-pages", type=int, default=1, help="Places pages per query (each page ~20)")
    p.add_argument("--category", help="single sic_codes category key, e.g. food_drink_manufacturing")
    p.add_argument("--region", help="single geography.primary value, e.g. Yorkshire")
    p.add_argument("--cutoff", type=int, default=None)
    args = p.parse_args()
    if args.cutoff is not None:
        CUTOFF = args.cutoff
    return run(args)


if __name__ == "__main__":
    sys.exit(main())

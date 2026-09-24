#!/usr/bin/env python3
"""/next: assemble research bundles for today's remaining first-touch quota.

Deterministic. For each pending companies_seen row, in CSV order: run
check.md on the Endole email if present, scrape the company's own site,
pull Companies House officers, and print one JSON bundle. Hermes reads
research.md and draft.md against each bundle, then calls deliver.py.

Hard stops from check.md are applied here (rejected_check). Everything
else is left to judgement.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from check import check_email
from common import SSL_CTX, USER_AGENT, Supabase, http_json, load_env, log, now_iso
from hunter import hunt_domain

CH_BASE = "https://api.company-information.service.gov.uk"
SCRAPE_TIMEOUT_S = 12
MAX_PAGES = 6
INTEREST_PATHS = ("about", "contact", "team", "careers", "people", "our-story", "who-we-are", "history")
MAILTO_RE = re.compile(r"mailto:([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
SITE_KEYWORDS = (
    "manual", "spreadsheet", "excel", "forecast", "stock control", "inventory", "stocktake",
    "demand planning", "production planning", "order management", "warehouse", "fleet",
    "cold store", "chilled", "24 hour", "seven days", "multi-site", "sites", "erp", "wms",
)
BI_SIGNATURES = ("powerbi", "power-bi", "power bi", "tableau", "lookerstudio", "looker studio", "qlik", "sisense", "datastudio")
JUNK_EMAIL = ("example.com", "domain.com", "sentry.io", "wixpress", "cloudflare", "schema.org", ".png", ".jpg", ".svg", ".css", ".js")


# ---------------------------------------------------------------------------
# Site scrape
# ---------------------------------------------------------------------------


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self._in_title = False
        self.og_site_name: str | None = None
        self.links: list[str] = []
        self.text: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip = True
        if tag == "meta" and (ad.get("property") or "").lower() == "og:site_name":
            self.og_site_name = ad.get("content", "").strip() or None
        if tag == "a" and ad.get("href"):
            self.links.append(ad["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        (self.title if self._in_title else self.text).append(data)


def fetch_html(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=SCRAPE_TIMEOUT_S, context=SSL_CTX) as resp:
            raw = resp.read(400_000)
            ctype = resp.headers.get("Content-Type", "").lower()
            if "html" not in ctype and not raw[:64].lstrip().lower().startswith((b"<!doctype", b"<html")):
                return resp.status, resp.geturl(), ""
            return resp.status, resp.geturl(), raw.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return 0, url, ""


def parse(html: str) -> PageParser:
    p = PageParser()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001
        pass
    return p


def clean_text(parts: list[str]) -> str:
    text = " ".join(t.strip() for t in parts if t and t.strip())
    return re.sub(r"\s+", " ", text)


def scrape_site(website: str | None) -> dict[str, Any]:
    if not website:
        return {"status": "no_website"}
    url = website if "://" in website else f"https://{website}"
    status, final_url, html = fetch_html(url)
    if not html:
        return {"status": f"unreachable_http_{status}", "final_url": final_url}

    home = parse(html)
    pages = [(final_url, home)]
    seen = {final_url}
    for href in home.links:
        low = href.lower()
        if any(tok in low for tok in INTEREST_PATHS) and len(pages) < MAX_PAGES:
            full = urljoin(final_url, href)
            if full in seen or urllib.parse.urlparse(full).netloc != urllib.parse.urlparse(final_url).netloc:
                continue
            seen.add(full)
            st, fu, hx = fetch_html(full)
            if hx:
                pages.append((fu, parse(hx)))

    all_html = html + "".join("" for _ in pages)
    texts = {u: clean_text(p.text) for u, p in pages}
    combined = " ".join(texts.values())
    low = combined.lower()

    emails: list[str] = []
    for blob in [html] + [clean_text(p.text) for _, p in pages]:
        for e in MAILTO_RE.findall(blob) + EMAIL_RE.findall(blob):
            e = e.lower().rstrip(".,;)")
            if any(j in e for j in JUNK_EMAIL) or e in emails:
                continue
            emails.append(e)

    name = home.og_site_name or (clean_text(home.title).split(" | ")[0].split(" - ")[0].strip() or None)
    excerpts = {}
    for u, t in texts.items():
        key = "home" if u == final_url else next((tok for tok in INTEREST_PATHS if tok in u.lower()), "page")
        if key not in excerpts:
            excerpts[key] = t[:1500]

    return {
        "status": "ok",
        "final_url": final_url,
        "site_name": name,
        "emails": emails[:10],
        "keyword_hits": [k for k in SITE_KEYWORDS if k in low],
        "bi_signatures": [s for s in BI_SIGNATURES if s in html.lower()],
        "has_team_page": any(tok in u.lower() for u, _ in pages for tok in ("team", "people")),
        "has_careers_page": any(tok in u.lower() for u, _ in pages for tok in ("career", "jobs")),
        "pages": [u for u, _ in pages],
        "excerpts": excerpts,
    }


# ---------------------------------------------------------------------------
# Companies House officers
# ---------------------------------------------------------------------------


def ch_headers() -> dict[str, str] | None:
    key = next((os.environ[n] for n in ("COMPANY_HOUSE", "COMPANIES_HOUSE_API_KEY", "CH_API_KEY") if os.environ.get(n)), None)
    if not key:
        return None
    token = base64.b64encode(f"{key}:".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def ch_officers(company_number: str) -> list[dict[str, Any]]:
    hdrs = ch_headers()
    if not hdrs:
        log("stage=ch", note="no COMPANY_HOUSE key, skipping officers")
        return []
    status, data = http_json(f"{CH_BASE}/company/{urllib.parse.quote(company_number)}/officers?items_per_page=20", headers=hdrs)
    if status >= 300:
        log("stage=ch_error", company_number=company_number, http=status)
        return []
    out = []
    for item in (data or {}).get("items") or []:
        if item.get("resigned_on"):
            continue
        out.append(
            {
                "name": item.get("name"),
                "role": item.get("officer_role"),
                "occupation": item.get("occupation"),
                "appointed_on": item.get("appointed_on"),
            }
        )
    return out


def ch_profile(company_number: str) -> dict[str, Any] | None:
    hdrs = ch_headers()
    if not hdrs:
        return None
    status, data = http_json(f"{CH_BASE}/company/{urllib.parse.quote(company_number)}", headers=hdrs)
    if status >= 300 or not isinstance(data, dict):
        return None
    return {
        "company_name": data.get("company_name"),
        "company_status": data.get("company_status"),
        "sic_codes": data.get("sic_codes"),
        "accounts_type": ((data.get("accounts") or {}).get("last_accounts") or {}).get("type"),
        "has_charges": data.get("has_charges"),
        "has_insolvency_history": data.get("has_insolvency_history"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def latest_campaign(db: Supabase) -> dict[str, Any] | None:
    rows = db.select("campaigns", select="id,name,icp_id", order="created_at.desc", limit="1")
    return rows[0] if rows else None


def run(args: argparse.Namespace) -> int:
    load_env()
    db = Supabase()
    quota = db.quota_remaining()
    limit = min(quota, args.limit) if args.limit is not None else quota
    if limit <= 0:
        print(json.dumps({"quota_remaining": quota, "bundles": [], "note": "quota already used today"}, indent=2))
        return 0

    campaign = {"id": args.campaign} if args.campaign else latest_campaign(db)
    if not campaign:
        raise SystemExit("no campaign found; ingest a CSV first")

    pending = db.select(
        "companies_seen",
        campaign_id=f"eq.{campaign['id']}",
        outcome="eq.pending",
        order="csv_order.asc",
        limit=str(limit + args.overscan),
    )
    bundles: list[dict[str, Any]] = []
    rejected_check = 0
    for row in pending:
        if len(bundles) >= limit:
            break
        cn = row["company_number"]
        endole_email = (row.get("email") or "").lower() or None
        if not row.get("website"):
            db.set_outcome(cn, "rejected_ingest", "no_website")
            log("stage=skip", company_number=cn, reason="no_website")
            continue

        check = None
        if endole_email:
            check = check_email(db, endole_email, row.get("domain"))
            if check["decision"] == "hard_stop":
                db.set_outcome(cn, "rejected_check", f"{endole_email}: {check['reason']}")
                rejected_check += 1
                log("stage=check", company_number=cn, decision="hard_stop", reason=check["reason"])
                continue

        db.set_outcome(cn, "in_research")
        site = scrape_site(row.get("website"))
        hunter = hunt_domain(row.get("domain"))
        bundles.append(
            {
                "company_number": cn,
                "company_name": row.get("company_name"),
                "website": row.get("website"),
                "domain": row.get("domain"),
                "sic_code": row.get("sic_code"),
                "icp_id": row.get("icp_id") or campaign.get("icp_id"),
                "endole": row.get("raw"),
                "endole_email": endole_email,
                "check": check,
                "site": site,
                "companies_house": {"profile": ch_profile(cn), "officers": ch_officers(cn)},
                "hunter": hunter,
            }
        )
        log(
            "stage=bundle",
            company_number=cn,
            site=site.get("status"),
            officers=len(bundles[-1]["companies_house"]["officers"]),
            hunter=hunter.get("status"),
        )

    print(
        json.dumps(
            {
                "campaign": campaign,
                "quota_remaining": quota,
                "prepared": len(bundles),
                "rejected_check": rejected_check,
                "pending_left": max(0, len(pending) - len(bundles) - rejected_check),
                "bundles": bundles,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="/next: research bundles for today's quota")
    p.add_argument("--campaign", help="campaign id; default latest")
    p.add_argument("--limit", type=int, help="cap below the remaining quota")
    p.add_argument("--overscan", type=int, default=5, help="extra pending rows to fetch in case some hard-stop")
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The next company for a run, as a library. run.py is the only caller.

step() returns exactly one research bundle or a stop report. A company
that has been handed out and has no outcome yet is returned again:
there is no way past it. The run stops at N delivered drafts, when
pending runs out, or after a streak of rejections.

This file has no command line on purpose. See main().

Deterministic. For the next pending companies_seen row, in CSV order:
run check.md on the Endole email if present, scrape the company's own
site, pull Companies House officers, query Hunter. Hard stops from
check.md are applied here (rejected_check).

A row with no website is never rejected here. site_lookup.py tries the
Endole email's domain and Hunter by company name, checks any candidate
against the company number, postcode and registered name, and failing
that hands the company to Hermes to search for (card section 0).
"""

from __future__ import annotations

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
from common import SSL_CTX, USER_AGENT, Supabase, http_json, load_env, log, now_iso, research_card
from hunter import hunt_company, hunt_domain
import run_state as rs
import site_lookup as sl

CH_BASE = "https://api.company-information.service.gov.uk"
SCRAPE_TIMEOUT_S = 12
MAX_PAGES = 6
INTEREST_PATHS = ("about", "contact", "team", "careers", "people", "our-story", "who-we-are", "history")
# Where a UK site usually prints its registered name and company number.
VERIFY_PATHS = ("terms", "privacy", "legal", "conditions")
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
    except urllib.error.HTTPError as exc:
        return exc.code, url, ""
    except Exception:  # noqa: BLE001
        return 0, url, ""


# A site that answers with one of these exists; it is refusing this script.
BLOCKED_CODES = {401, 403, 406, 409, 429, 451, 503}


def url_variants(website: str) -> list[str]:
    """The address as given, then the common alternatives for a bare domain.

    Plenty of small company sites only answer on www, or only on http.
    Calling those dead throws away a real company.
    """
    given = website if "://" in website else f"https://{website}"
    parsed = urllib.parse.urlparse(given)
    if parsed.path.strip("/") or parsed.query:
        return [given]
    host = parsed.netloc.lower()
    bare = host[4:] if host.startswith("www.") else host
    out = [given]
    for v in (f"https://www.{bare}", f"https://{bare}", f"http://www.{bare}", f"http://{bare}"):
        if v.rstrip("/") not in [o.rstrip("/") for o in out]:
            out.append(v)
    return out


def fetch_first(website: str) -> tuple[int, str, str, list[dict[str, Any]]]:
    tried: list[dict[str, Any]] = []
    for url in url_variants(website):
        status, final_url, html = fetch_html(url)
        tried.append({"url": url, "http": status})
        if html:
            return status, final_url, html, tried
    return 0, website, "", tried


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


def scrape_site(website: str | None, *, verify: bool = False) -> dict[str, Any]:
    """verify=True also reads the legal pages and returns the full text as `_text`."""
    if not website:
        return {"status": "no_website"}
    wanted = INTEREST_PATHS + (VERIFY_PATHS if verify else ())
    max_pages = MAX_PAGES + (3 if verify else 0)
    status, final_url, html, attempts = fetch_first(website)
    if not html:
        codes = [a["http"] for a in attempts]
        blocked = next((c for c in codes if c in BLOCKED_CODES), None)
        if blocked:
            # Not dead: the site answered and refused. A person or a browser can still read it.
            return {"status": f"blocked_http_{blocked}", "final_url": attempts[0]["url"], "attempts": attempts}
        return {"status": f"unreachable_http_{max(codes) if codes else 0}", "final_url": attempts[0]["url"], "attempts": attempts}

    home = parse(html)
    pages = [(final_url, home)]
    seen = {final_url}
    for href in home.links:
        low = href.lower()
        if any(tok in low for tok in wanted) and len(pages) < max_pages:
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
        **({"_text": combined} if verify else {}),
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


PAGE = 20


def build_bundle(db: Supabase, row: dict[str, Any], campaign: dict[str, Any], check: dict[str, Any] | None,
                 site: dict[str, Any] | None = None, hunter: dict[str, Any] | None = None,
                 tried: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """site and hunter are passed in when the website lookup already fetched them."""
    cn = row["company_number"]
    domain = sl.company_domain(row) if row.get("website") else None
    site = site or scrape_site(row.get("website"))
    site.pop("_text", None)
    hunter = hunter or hunt_domain(domain)
    bundle = {
        "company_number": cn,
        "company_name": row.get("company_name"),
        "website": row.get("website"),
        "domain": domain,
        "site_record": (row.get("raw") or {}).get("_site"),
        **({"site_search": {
            "needed": True,
            "why": "No website on record and the script could not confirm one. Card section 0.",
            "registered_postcode": sl.row_postcode(row),
            "already_tried": tried or [],
        }} if not row.get("website") else {}),
        "sic_code": row.get("sic_code"),
        "icp_id": row.get("icp_id") or campaign.get("icp_id"),
        "endole": row.get("raw"),
        "endole_email": (row.get("email") or "").lower() or None,
        "check": check,
        "site": site,
        "companies_house": {"profile": ch_profile(cn), "officers": ch_officers(cn)},
        "hunter": hunter,
    }
    log("stage=bundle", company_number=cn, site=site.get("status"),
        officers=len(bundle["companies_house"]["officers"]), hunter=hunter.get("status"))
    return bundle


def run_rows(db: Supabase, run: dict[str, Any]) -> list[dict[str, Any]]:
    """Everything this run has resolved so far, oldest first."""
    return db.select(
        "companies_seen",
        campaign_id=f"eq.{run['campaign_id']}",
        last_checked_at=f"gte.{run['started_at']}",
        outcome=f"in.({','.join(rs.RUN_OUTCOMES)})",
        select="company_number,company_name,outcome,reason,last_checked_at",
        order="last_checked_at.asc",
    )


def in_hand(db: Supabase, campaign_id: str) -> dict[str, Any] | None:
    rows = db.select("companies_seen", campaign_id=f"eq.{campaign_id}", outcome="eq.in_research",
                     order="last_checked_at.asc", limit="1")
    return rows[0] if rows else None


def next_pending(db: Supabase, campaign: dict[str, Any]) -> dict[str, Any] | None:
    """Claim the next workable pending row and return its bundle, or None."""
    while True:
        page = db.select("companies_seen", campaign_id=f"eq.{campaign['id']}", outcome="eq.pending",
                         order="csv_order.asc", limit=str(PAGE))
        if not page:
            return None
        for row in page:
            cn = row["company_number"]
            check = None
            endole_email = (row.get("email") or "").lower() or None
            if endole_email:
                check = check_email(db, endole_email, row.get("domain"))
                if check["decision"] == "hard_stop":
                    db.set_outcome(cn, "rejected_check", f"{endole_email}: {check['reason']}")
                    log("stage=check", company_number=cn, decision="hard_stop", reason=check["reason"])
                    continue
            db.set_outcome(cn, "in_research")
            found, tried = (None, [])
            if not row.get("website"):
                # Never a rejection: a missing website is something to look up.
                found, tried = sl.resolve(row, scrape_site, hunt_company, fetch_html)
                if found:
                    row = sl.record(db, row, found)
                else:
                    log("site=unresolved", company_number=cn, tried=len(tried))
            bundle = build_bundle(db, row, campaign, check, site=(found or {}).get("site"),
                                  hunter=(found or {}).get("hunter"), tried=tried)
            rs.cache_bundle(bundle)
            return bundle


def step(db: Supabase, target: int | None, campaign_arg: str | None, now=None) -> dict[str, Any]:
    """One turn of the loop. Returns {"bundle": ...} or a stop report."""
    now = now or rs.utcnow()
    existing = rs.load_run()

    if target is None:
        if not existing:
            return rs.report(None, [], "no_active_run")
        run = existing
        if run.get("stopped"):
            return rs.report(run, run_rows(db, run), run["stopped"])
        if not rs.is_live(run, now):
            return rs.report(None, [], "no_active_run")
    else:
        if target <= 0:
            raise SystemExit("--target must be a positive number of drafts")
        campaign_id = campaign_arg
        if not campaign_id:
            latest = latest_campaign(db)
            if not latest:
                raise SystemExit("no campaign found; ingest a CSV first")
            campaign_id = latest["id"]
        run, started = rs.decide_run(existing, target, campaign_id, now)
        if started:
            log("run=started", target=target, campaign_id=campaign_id)
        else:
            log("guardrail=target_repeated", note="--target passed mid-run; count kept", target=target)

    campaign = {"id": run["campaign_id"]}
    run["touched_at"] = now.isoformat()

    held = in_hand(db, run["campaign_id"])
    if held:
        rs.save_run(run)
        cn = held["company_number"]
        log("guardrail=unfinished_company_rehanded", company_number=cn)
        bundle = rs.cached_bundle(cn)
        if not bundle:
            bundle = build_bundle(db, held, campaign, None)
            rs.cache_bundle(bundle)
        return {"bundle": bundle}

    rows = run_rows(db, run)
    why = rs.stop_reason(run, rows)
    if not why:
        bundle = next_pending(db, campaign)
        if bundle:
            rs.save_run(run)
            return {"bundle": bundle}
        why = "no_pending"
        rows = run_rows(db, run)
    if why == "reject_streak":
        log("guardrail=reject_streak_stop", streak=rs.reject_streak(rows))
    run["stopped"] = why
    rs.save_run(run)
    return rs.report(run, rows, why)


def main() -> int:
    # Deliberately not runnable. If a research job could call this it would see
    # the sequence, and could pull the next company before finishing its own.
    log("guardrail=next_called_directly")
    print("next.py is not run by hand or by a research job. A run is started with: "
          "python3 scripts/run.py start --target <n>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

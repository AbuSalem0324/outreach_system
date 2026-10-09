#!/usr/bin/env python3
"""/next: hand Hermes one company at a time until N drafts are delivered.

  next.py --target N   start a run (or carry on a live one with the same N)
  next.py              the next company in the run, or the stop report

The loop is here, not in the model. Each call returns exactly one
research bundle, with research-card.md printed above it, or a stop
report. A company that has been handed out and not yet finished is
handed out again: there is no way to skip ahead. The run stops at N
delivered drafts, when pending runs out, or after a streak of
rejections. Hermes is never told how many companies are left.

Deterministic. For the next pending companies_seen row, in CSV order:
run check.md on the Endole email if present, scrape the company's own
site, pull Companies House officers, query Hunter. Hard stops from
check.md are applied here (rejected_check).
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
from common import SSL_CTX, USER_AGENT, Supabase, http_json, load_env, log, now_iso, research_card
from hunter import hunt_domain
import run_state as rs

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


PAGE = 20
NEXT_CMD = "python3 scripts/next.py"


def build_bundle(db: Supabase, row: dict[str, Any], campaign: dict[str, Any], check: dict[str, Any] | None) -> dict[str, Any]:
    cn = row["company_number"]
    site = scrape_site(row.get("website"))
    hunter = hunt_domain(row.get("domain"))
    bundle = {
        "company_number": cn,
        "company_name": row.get("company_name"),
        "website": row.get("website"),
        "domain": row.get("domain"),
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
            if not row.get("website"):
                db.set_outcome(cn, "rejected_ingest", "no_website")
                log("stage=skip", company_number=cn, reason="no_website")
                continue
            check = None
            endole_email = (row.get("email") or "").lower() or None
            if endole_email:
                check = check_email(db, endole_email, row.get("domain"))
                if check["decision"] == "hard_stop":
                    db.set_outcome(cn, "rejected_check", f"{endole_email}: {check['reason']}")
                    log("stage=check", company_number=cn, decision="hard_stop", reason=check["reason"])
                    continue
            db.set_outcome(cn, "in_research")
            bundle = build_bundle(db, row, campaign, check)
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
        return {"bundle": bundle, "note": "This company was already handed out and has no outcome yet. "
                                          "Finish it with one command from the card before asking for another."}

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


def run(args: argparse.Namespace) -> int:
    load_env()
    target = args.target if args.target is not None else args.limit
    out = step(Supabase(), target, args.campaign)
    if out.get("bundle") and not args.no_card:
        print(research_card())
        print("===== COMPANY (JSON) =====")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if out.get("bundle"):
        print(f"\nWhen this company has its one outcome, run: {NEXT_CMD}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="/next: one company at a time until N drafts are delivered")
    p.add_argument("--target", type=int, help="drafts to deliver this run; omit to continue the current run")
    p.add_argument("--limit", type=int, help="old name for --target; still returns one company per call")
    p.add_argument("--campaign", help="campaign id; default latest")
    p.add_argument("--no-card", action="store_true", help="JSON only, without research-card.md above it")
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())

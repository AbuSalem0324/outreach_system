#!/usr/bin/env python3
"""Find and check a company's website when the Endole export has none.

Ladder, first hit wins:
  1. the Endole email's domain, unless it is a freemail or ISP address
  2. Hunter domain-search by company name
  3. a web search by this script, name plus registered postcode
  4. Hermes, by web search, then `site_lookup.py set`

Every candidate is fetched and checked against Companies House facts
the script already holds: the company number, the registered postcode,
the registered name. UK companies must show their registered name and
number on their website, so a match is strong evidence it is the right
company and not a namesake.

  set   --company-number N --url U [--evidence "..."]
  none  --company-number N --searched "what was tried"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from typing import Any, Callable

from common import Supabase, _name_key, domain_from_email, domain_from_website, load_env, log, now_iso

FREEMAIL = {
    "gmail.com", "googlemail.com", "aol.com", "aol.co.uk", "icloud.com", "me.com", "mac.com", "msn.com",
    "btconnect.com", "btinternet.com", "btopenworld.com", "talk21.com", "tiscali.co.uk", "talktalk.net",
    "sky.com", "virginmedia.com", "virgin.net", "ntlworld.com", "blueyonder.co.uk", "zen.co.uk",
    "o2.co.uk", "orange.net", "wanadoo.co.uk", "freeserve.co.uk", "lineone.net", "supanet.com",
    "mail.com", "gmx.com", "gmx.co.uk", "protonmail.com", "proton.me", "ymail.com", "rocketmail.com",
    "plus.com", "uwclub.net", "onetel.com", "tesco.net", "zoho.com", "pm.me",
}
FREEMAIL_BRANDS = ("yahoo.", "hotmail.", "live.", "outlook.", "fsnet.", "fsmail.")
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", re.I)
NUMBER_RE = re.compile(r"\b(?:[A-Z]{2}\d{6}|\d{6,8})\b", re.I)
VERIFIED, PLAUSIBLE, UNVERIFIED = "verified", "plausible", "unverified"
HUNTER_BY_NAME = os.environ.get("OUTREACH_HUNTER_COMPANY_SEARCH", "1") != "0"
SCRIPT_SEARCH = os.environ.get("OUTREACH_SCRIPT_SEARCH", "1") != "0"
SEARCH_URL = "https://html.duckduckgo.com/html/?q={q}"
MAX_SEARCH_CANDIDATES = 4
HREF_RE = re.compile(r'href="([^"]+)"', re.I)
# Pages about a company that are never the company's own site.
NOT_THEIR_SITE = (
    "duckduckgo.com", "google.", "bing.com", "gov.uk", "endole.co.uk", "facebook.com", "linkedin.com",
    "twitter.com", "x.com", "instagram.com", "youtube.com", "tiktok.com", "wikipedia.org", "yell.com",
    "yelp.", "192.com", "cylex", "companycheck", "company-check", "opencorporates.com", "dnb.com",
    "bloomberg.com", "zoominfo.com", "rocketreach.co", "crunchbase.com", "thegazette.co.uk",
    "tripadvisor.", "trustpilot.com", "checkatrade.com", "scoot.co.uk", "thomsonlocal.com",
    "misterwhat", "pomanda.com", "globaldatabase.com", "northdata.", "b2bhint.com", "creditsafe.",
    "experian.", "kompass.com", "europages.", "hotfrog.", "freeindex.co.uk", "brownbook.net",
    "bizdb.co.uk", "bizstats.co.uk", "solocheck", "companiesintheuk.co.uk", "duedil.com", "apollo.io",
    "signalhire.com", "lusha.com", "indeed.", "glassdoor.", "amazon.", "ebay.", "companieslist.co.uk",
    "ukcompanydir", "datalog.co.uk", "find-and-update.company-information", "doogal.co.uk",
    "getthedata.com", "streetcheck.co.uk", "rightmove.co.uk", "zoopla.co.uk", "foodanddrink",
    "fhrs", "food.gov", "scoresonthedoors", "cqc.org.uk", "nhs.uk", "britishlistedbuildings",
)


def search_domains(html: str) -> list[str]:
    """Result domains from a DuckDuckGo HTML page, in order, directories removed."""
    out: list[str] = []
    for href in HREF_RE.findall(html or ""):
        href = href.replace("&amp;", "&")
        if "uddg=" in href:
            target = (urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg") or [""])[0]
        elif href.startswith("http"):
            target = href
        else:
            continue
        domain = domain_from_website(target)
        if not domain or "." not in domain or is_freemail(domain) or any(tok in domain for tok in NOT_THEIR_SITE):
            continue
        if domain not in out:
            out.append(domain)
    return out


def is_freemail(domain: str | None) -> bool:
    d = (domain or "").lower().strip()
    if not d:
        return False
    return d in FREEMAIL or any(d.startswith(b) or f".{b}" in d for b in FREEMAIL_BRANDS)


def company_domain(row: dict[str, Any]) -> str | None:
    """A domain that could be the company's own. Never a freemail provider."""
    d = domain_from_website(row.get("website")) or row.get("domain") or domain_from_email(row.get("email"))
    return None if is_freemail(d) else d


def row_postcode(row: dict[str, Any]) -> str | None:
    raw = row.get("raw") or {}
    for header in (raw.get("_mapped") or {}).get("postcode") or []:
        if (raw.get(header) or "").strip():
            return raw[header].strip()
    for key in ("Postcode", "_address", "Name and Address"):
        hits = POSTCODE_RE.findall(str(raw.get(key) or ""))
        if hits:
            return " ".join(hits[-1])
    return None


def grade_text(text: str, company_number: str | None, company_name: str | None, postcode: str | None) -> tuple[str, list[str]]:
    """How well a site's text matches the company on record."""
    matched: list[str] = []
    cn = (company_number or "").upper()
    if cn and any(tok.upper().zfill(8) == cn for tok in NUMBER_RE.findall(text)):
        matched.append("company_number")
    pc = re.sub(r"\s", "", postcode or "").upper()
    if pc and pc in re.sub(r"\s", "", text).upper():
        matched.append("postcode")
    name = _name_key(company_name)
    if name and f" {name} " in f" {_name_key(text)} ":
        matched.append("registered_name")
    if "company_number" in matched or "postcode" in matched:
        return VERIFIED, matched
    return (PLAUSIBLE if matched else UNVERIFIED), matched


def check_candidate(url: str, row: dict[str, Any], scrape: Callable[..., dict[str, Any]], source: str) -> dict[str, Any]:
    site = scrape(url, verify=True)
    text = site.pop("_text", "")
    status = str(site.get("status"))
    live = status == "ok"
    grade, matched = grade_text(text, row.get("company_number"), row.get("company_name"), row_postcode(row)) if live else (UNVERIFIED, [])
    return {
        "url": site.get("final_url") or url,
        "domain": domain_from_website(site.get("final_url") or url),
        "source": source,
        "live": live,
        "status": "ok" if live else ("exists_but_blocked_the_script" if status.startswith("blocked") else "no_answer"),
        "grade": grade,
        "matched": matched,
        "site": site,
    }


def public(cand: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cand.items() if k != "site"}


def resolve(row: dict[str, Any], scrape: Callable[..., dict[str, Any]],
            hunt_company: Callable[[str], dict[str, Any]] | None,
            fetch: Callable[[str], tuple[int, str, str]] | None = None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Steps 1 to 3. Returns (accepted candidate or None, everything tried)."""
    tried: list[dict[str, Any]] = []
    email_domain = domain_from_email(row.get("email"))
    if email_domain and is_freemail(email_domain):
        tried.append({"source": "endole_email_domain", "domain": email_domain, "skipped": "freemail or ISP address"})
    elif email_domain:
        cand = check_candidate(f"https://{email_domain}", row, scrape, "endole_email_domain")
        tried.append(public(cand))
        # The company's own mailbox is on this domain, so a name match is enough.
        if cand["live"] and cand["grade"] in (VERIFIED, PLAUSIBLE):
            return cand, tried
    if hunt_company and HUNTER_BY_NAME and row.get("company_name"):
        found = hunt_company(row["company_name"])
        domain = found.get("domain") if found.get("status") == "ok" else None
        if domain and not is_freemail(domain) and domain != email_domain:
            cand = check_candidate(f"https://{domain}", row, scrape, "hunter_company_search")
            cand["hunter"] = found
            tried.append({k: v for k, v in public(cand).items() if k != "hunter"})
            # Hunter matched on the name alone, so the name proves nothing here.
            if cand["live"] and cand["grade"] == VERIFIED:
                return cand, tried
        else:
            tried.append({"source": "hunter_company_search", "status": found.get("status"), "domain": domain})
    if fetch and SCRIPT_SEARCH and row.get("company_name"):
        seen = {t.get("domain") for t in tried}
        name = re.sub(r"\s+", " ", row["company_name"]).strip()
        queries = [f'"{name}" {row_postcode(row) or ""}'.strip(), name]
        domains: list[str] = []
        for q in queries:
            http, _, html = fetch(SEARCH_URL.format(q=urllib.parse.quote_plus(q)))
            hits = search_domains(html)
            log("site=search", query=q, http=http, results=len(hits))
            domains += [d for d in hits if d not in domains and d not in seen]
            if len(domains) >= MAX_SEARCH_CANDIDATES:
                break
        if not domains:
            tried.append({"source": "script_web_search", "status": "no_results", "queries": queries})
        for domain in domains[:MAX_SEARCH_CANDIDATES]:
            cand = check_candidate(f"https://{domain}", row, scrape, "script_web_search")
            tried.append(public(cand))
            # A search result is a guess until the site itself names the company.
            if cand["live"] and cand["grade"] == VERIFIED:
                return cand, tried
    return None, tried


def record(db: Any, row: dict[str, Any], cand: dict[str, Any], evidence: str | None = None) -> dict[str, Any]:
    """Write the accepted site back to companies_seen and return the updated row."""
    stamp = {"url": cand["url"], "source": cand["source"], "grade": cand["grade"],
             "matched": cand["matched"], "evidence": evidence, "at": now_iso()}
    patch = {"website": cand["url"], "domain": cand["domain"], "raw": {**(row.get("raw") or {}), "_site": stamp}}
    db.patch("companies_seen", {"company_number": f"eq.{row['company_number']}"}, patch)
    log("site=resolved", company_number=row["company_number"], source=cand["source"], grade=cand["grade"], url=cand["url"])
    return {**row, **patch}


# ---------------------------------------------------------------------------
# CLI: what Hermes calls after its own web search
# ---------------------------------------------------------------------------

NEXT_CMD = "python3 scripts/next.py"


def in_hand(db: Any, company_number: str, verb: str) -> dict[str, Any]:
    rows = db.select("companies_seen", company_number=f"eq.{company_number}", limit="1")
    if not rows:
        raise SystemExit(f"no companies_seen row for {company_number}")
    if rows[0].get("outcome") != "in_research":
        log("guardrail=not_in_hand", verb=verb, company_number=company_number, outcome=rows[0].get("outcome"))
        raise SystemExit(f"{verb} refused: {company_number} is not the company in hand (outcome={rows[0].get('outcome')})")
    return rows[0]


def cmd_set(db: Any, args: argparse.Namespace) -> dict[str, Any]:
    import next as nx
    import run_state as rs

    row = in_hand(db, args.company_number, "site set")
    cand = check_candidate(args.url, row, nx.scrape_site, "web_search")
    if is_freemail(cand["domain"]):
        raise SystemExit("that is an email provider, not a company website")
    evidence = (args.evidence or "").strip()
    blocked = cand["status"] == "exists_but_blocked_the_script"
    if blocked and len(evidence) < 20:
        raise SystemExit(
            f"{args.url} exists but refuses this script, so it cannot be checked here. Open it yourself. If it is this "
            'company, run set again with --evidence "<what on the site ties it to this company>".'
        )
    if not cand["live"] and not blocked:
        raise SystemExit(f"could not load {args.url} on https, http, or www; check the address, or try another result")
    if cand["grade"] == UNVERIFIED and len(evidence) < 20:
        log("guardrail=site_unverified_refused", company_number=args.company_number, url=cand["url"])
        raise SystemExit(
            f"not accepted yet: {cand['url']} loads, but none of the company number {row['company_number']}, "
            f"the postcode {row_postcode(row) or '(none on record)'}, or the registered name appears on it. "
            "It may be a different company with a similar name. If something specific on the site ties it to this "
            'company (same street address, same director, same trading name on Companies House), pass --evidence "<what>". '
            "Otherwise try another result, or finish with: site_lookup.py none"
        )
    row = record(db, row, cand, evidence or None)
    bundle = nx.build_bundle(db, row, {"id": row.get("campaign_id")}, None, site=cand["site"], hunter=cand.get("hunter"))
    bundle["handed_at"] = (rs.cached_bundle(args.company_number) or {}).get("handed_at")
    rs.cache_bundle(bundle)
    note = f"Site recorded ({cand['grade']}). Carry on from section 1 of the card."
    if blocked:
        note += " The script could not read this site, so the bundle has no site text: read the site yourself."
    return {"bundle": bundle, "note": note}


def cmd_none(db: Any, args: argparse.Namespace) -> dict[str, Any]:
    searched = (args.searched or "").strip()
    if len(searched) < 12:
        raise SystemExit("--searched must say which searches you ran")
    in_hand(db, args.company_number, "site none")
    db.set_outcome(args.company_number, "no_site_found", searched)
    return {"company_number": args.company_number, "outcome": "no_site_found", "next": NEXT_CMD}


def main() -> int:
    load_env()
    p = argparse.ArgumentParser(description="record or give up on a company website")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set")
    s.add_argument("--company-number", required=True)
    s.add_argument("--url", required=True)
    s.add_argument("--evidence", default="", help="needed only when the script cannot match the site itself")
    n = sub.add_parser("none")
    n.add_argument("--company-number", required=True)
    n.add_argument("--searched", required=True, help="the searches you ran")
    args = p.parse_args()
    out = (cmd_set if args.cmd == "set" else cmd_none)(Supabase(), args)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

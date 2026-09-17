#!/usr/bin/env python3
"""ingest.md: one Endole CSV in, one campaign out.

Header names are not stable across Endole exports, so columns are mapped
by fuzzy match to a fixed internal set and the whole row is kept in
companies_seen.raw. No contacts writes, no enrichment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    Supabase,
    ch_resolve_company_number,
    domain_from_email,
    domain_from_website,
    load_env,
    log,
    normalise_company_number,
)

# internal field -> list of header fragments, lowercase, punctuation stripped.
# First fragment that is contained in a normalised header wins.
HEADER_MAP: dict[str, tuple[str, ...]] = {
    "company_number": ("company number", "companynumber", "registration number", "reg no", "company no", "crn"),
    "name_and_address": ("name address", "name amp address"),
    "company_name": ("company name", "companyname", "registered name", "name"),
    "main_contact": ("main contact", "contact name", "key contact"),
    "company_email": ("company email", "generic email"),
    "website": ("website", "web address", "url", "domain"),
    "email": ("email address", "email"),
    "sic_code": ("sic code", "sic", "industry code"),
    "sic_description": ("sic description", "industry description", "industry", "business activity", "nature of business"),
    "status": ("company status", "status"),
    "employees": ("employees", "employee count", "no of employees", "headcount", "staff"),
    "turnover": ("turnover", "revenue"),
    "assets": ("total assets", "net assets", "assets"),
    "company_size": ("company size", "size"),
    "incorporated": ("incorporation", "incorporated", "date of creation", "company age", "age"),
    "region": ("region", "county", "area"),
    "town": ("town", "city", "locality"),
    "postcode": ("postcode", "post code", "postal code"),
    "telephone": ("telephone", "phone", "tel"),
    "directors": ("director names", "director", "officer", "decision maker", "key person"),
}


def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (h or "").strip().lower()).strip()


def build_mapping(headers: list[str]) -> dict[str, list[str]]:
    """internal field -> original headers that feed it (directors may be several).

    Exact matches win over substring matches across the whole header set, so
    Endole's blank 'Sales Status' can't steal 'Status'.
    """
    mapping: dict[str, list[str]] = {}
    taken: set[str] = set()
    normed = {h: norm_header(h) for h in headers}
    for field, fragments in HEADER_MAP.items():
        for mode in ("exact", "contains"):
            hits: list[str] = []
            for frag in fragments:
                for h in headers:
                    if h in taken or h in hits:
                        continue
                    nh = normed[h]
                    ok = nh == frag if mode == "exact" else (len(frag) > 3 and frag in nh)
                    if ok:
                        hits.append(h)
                if hits and field != "directors":
                    break
            if hits:
                mapping[field] = hits if field == "directors" else hits[:1]
                taken.update(mapping[field])
                break
    return mapping


def first_value(row: dict[str, str], headers: list[str] | None) -> str | None:
    for h in headers or []:
        v = (row.get(h) or "").strip()
        if v:
            return v
    return None


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    rows = [{k: (v or "") for k, v in r.items() if k is not None} for r in reader]
    return headers, rows


def run(args: argparse.Namespace) -> int:
    load_env()
    db = Supabase()
    path = Path(args.csv)
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")

    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    existing = db.select("campaigns", file_sha256=f"eq.{sha}", select="id,name,created_at")
    if existing:
        print(json.dumps({"refused": "same file already ingested", "campaign": existing[0]}, indent=2))
        return 2

    headers, rows = read_csv(path)
    mapping = build_mapping(headers)
    log("ingest=mapping", mapped=mapping, unmapped=[h for h in headers if not any(h in v for v in mapping.values())])
    if "company_number" not in mapping and "company_name" not in mapping and "name_and_address" not in mapping:
        raise SystemExit("need a company number or a company name column; headers: " + ", ".join(headers))
    resolve = "company_number" not in mapping
    if resolve:
        log("ingest=note", note="no company number column; resolving via Companies House name + postcode")

    campaign = db.insert(
        "campaigns",
        {
            "name": args.name or path.stem,
            "icp_id": args.icp,
            "file_name": path.name,
            "file_sha256": sha,
            "row_count": len(rows),
        },
    )[0]
    campaign_id = campaign["id"]

    # Batch lookup of company numbers already evaluated
    numbers = []
    parsed: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        cn = normalise_company_number(first_value(row, mapping.get("company_number")))
        name = first_value(row, mapping.get("company_name"))
        address = None
        if not name and mapping.get("name_and_address"):
            name, address = split_name_address(first_value(row, mapping["name_and_address"]))
        postcode = first_value(row, mapping.get("postcode"))
        if not cn and name:
            cn, ch_hit = ch_resolve_company_number(name, postcode)
            row["_ch_resolution"] = ch_hit
        website = first_value(row, mapping.get("website"))
        personal = (first_value(row, mapping.get("email")) or "").lower() or None
        generic = (first_value(row, mapping.get("company_email")) or "").lower() or None
        email = personal or generic
        directors: list[str] = []
        for h in mapping.get("directors", []):
            for d in (first_value(row, [h]) or "").split(","):
                d = d.strip()
                if d and d not in directors:
                    directors.append(d)
        parsed.append(
            {
                "csv_order": idx,
                "company_number": cn,
                "company_name": name,
                "website": website,
                "email": email,
                "sic_code": (first_value(row, mapping.get("sic_code")) or "").split(",")[0].strip() or None,
                "domain": domain_from_website(website) or domain_from_email(email),
                "raw": {
                    **row,
                    "_directors": directors,
                    "_main_contact": first_value(row, mapping.get("main_contact")),
                    "_personal_email": personal,
                    "_generic_email": generic,
                    "_address": address,
                    "_mapped": {k: v for k, v in mapping.items()},
                },
            }
        )
        if cn:
            numbers.append(cn)

    seen: dict[str, dict[str, Any]] = {}
    for i in range(0, len(numbers), 200):
        chunk = numbers[i : i + 200]
        for r in db.select(
            "companies_seen",
            company_number=f"in.({','.join(chunk)})",
            select="company_number,outcome,reason",
        ):
            seen[r["company_number"]] = r

    summary = {
        "campaign_id": campaign_id,
        "name": campaign["name"],
        "icp_id": args.icp,
        "rows": len(rows),
        "new": 0,
        "seen_before": 0,
        "no_company_number": 0,
        "no_website": 0,
        "no_email": 0,
        "seen_before_detail": [],
    }
    to_insert: list[dict[str, Any]] = []
    for p in parsed:
        base = {
            "campaign_id": campaign_id,
            "icp_id": args.icp,
            "csv_order": p["csv_order"],
            "company_number": p["company_number"],
            "company_name": p["company_name"],
            "website": p["website"],
            "email": p["email"],
            "sic_code": p["sic_code"],
            "domain": p["domain"],
            "raw": p["raw"],
        }
        if not p["company_number"]:
            summary["no_company_number"] += 1
            base.update({"outcome": "rejected_ingest", "reason": "no_company_number (unresolved at Companies House)" if resolve else "no_company_number"})
            to_insert.append(base)
            continue
        prior = seen.get(p["company_number"])
        if prior and prior.get("outcome") != "pending":
            summary["seen_before"] += 1
            summary["seen_before_detail"].append(
                {"company_number": p["company_number"], "outcome": prior.get("outcome"), "reason": prior.get("reason")}
            )
            continue
        if prior:
            # pending from an earlier campaign: leave it, it'll get picked up
            summary["seen_before"] += 1
            continue
        summary["new"] += 1
        if not p["website"]:
            summary["no_website"] += 1
        if not p["email"]:
            summary["no_email"] += 1
        base["outcome"] = "pending"
        to_insert.append(base)

    for i in range(0, len(to_insert), 100):
        db.insert("companies_seen", to_insert[i : i + 100])

    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="ingest.md: Endole CSV -> campaign")
    p.add_argument("csv")
    p.add_argument("--name", help="campaign name; defaults to the filename")
    p.add_argument("--icp", default="home-turf-fmcg-v1", help="icp_id tag for this batch")
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())

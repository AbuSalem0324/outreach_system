#!/usr/bin/env python3
"""One Hunter domain-search per domain for contacts not yet enriched.

Does not run unless invoked. Never touches unsubscribed, do_not_contact,
or replied. Resume state is /root/outreach/backfill-domains.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import Supabase, load_env, log, now_iso
from hunter import hunt_domain

STATE = Path("/root/outreach/backfill-domains.json")


def load_state() -> dict:
    if not STATE.is_file():
        return {"domains": []}
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def eligible(db: Supabase) -> list[dict]:
    return db.select(
        "contacts",
        status="in.(new,contacted)",
        email_verification_status="eq.ok",
        enriched_at="is.null",
        select="id,email,domain,company_name",
    )


def main() -> int:
    load_env()
    db = Supabase()
    rows = [r for r in eligible(db) if r.get("domain") and r.get("email")]
    by_domain: dict[str, list[dict]] = {}
    for row in rows:
        by_domain.setdefault(row["domain"].strip().lower(), []).append(row)
    state = load_state()
    done = set(state.get("domains") or [])
    pending = [d for d in by_domain if d not in done]
    print(json.dumps({"contacts": len(rows), "domains": len(by_domain), "domains_remaining": len(pending)}, indent=2))
    if "--run" not in sys.argv:
        print(json.dumps({"ran": False, "reason": "pass --run after Adam confirms the count"}))
        return 0

    updated = 0
    empty = 0
    errors = 0
    for domain in pending:
        found = hunt_domain(domain)
        if found.get("status") != "ok":
            errors += 1
            log("backfill=error", domain=domain, status=found.get("status"))
            continue
        people = {p["email"]: p for p in found.get("personals") or [] if p.get("email")}
        for row in by_domain[domain]:
            person = people.get(row["email"].strip().lower())
            linkedin = (person or {}).get("linkedin_url")
            phone = (person or {}).get("phone")
            if not linkedin and not phone:
                empty += 1
                continue
            payload = {
                "linkedin_url": linkedin,
                "phone": phone,
                "phone_type": "mobile" if phone else None,
                "enrichment_source": "hunter",
                "enriched_at": now_iso(),
            }
            db.patch("contacts", {"id": f"eq.{row['id']}"}, payload)
            updated += 1
        done.add(domain)
        state["domains"] = sorted(done)
        save_state(state)
    print(json.dumps({"ran": True, "domains_searched": len(pending) - errors, "rows_updated": updated, "rows_empty": empty, "errors": errors}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

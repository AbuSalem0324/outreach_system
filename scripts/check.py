#!/usr/bin/env python3
"""check.md: one email in, a decision out. No APIs beyond Supabase, no AI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from common import Supabase, domain_from_email, load_env

HARD_STOP = frozenset({"unsubscribed", "do_not_contact", "replied"})
CLEAR = frozenset({"new"})
FLAG = frozenset({"contacted", "skipped", "closed"})
FIELDS = "status,unsubscribed_at,last_contacted_at,contact_count,notes,angle,domain,email"


def check_email(db: Supabase, candidate_email: str, candidate_domain: str | None = None) -> dict[str, Any]:
    email = (candidate_email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("candidate_email must be a single email address")

    rows = db.select("contacts", email=f"eq.{email}", select=FIELDS, limit="1")
    row = rows[0] if rows else None
    domain = (candidate_domain or (row or {}).get("domain") or domain_from_email(email) or "").lower() or None

    others: list[dict[str, Any]] = []
    if domain:
        others = db.select("contacts", domain=f"eq.{domain}", email=f"neq.{email}", select="email,status")
    unsub = [o for o in others if o.get("status") == "unsubscribed"]

    result: dict[str, Any] = {
        "email": email,
        "decision": None,
        "reason": None,
        "row_found": bool(row),
        "domain": domain,
        "domain_context": {
            "other_contacts": len(others),
            "other_unsubscribed": len(unsub),
            "caution": f"{len(others)} other contact(s) at this domain, {len(unsub)} unsubscribed." if others else None,
        },
    }
    if row is None:
        result.update(decision="clear", reason="first_touch")
        return result

    status = (row.get("status") or "").strip()
    result.update({k: row.get(k) for k in ("status", "unsubscribed_at", "last_contacted_at", "contact_count", "notes", "angle")})
    if status in HARD_STOP:
        result.update(decision="hard_stop", reason=status)
    elif status in CLEAR:
        result.update(decision="clear", reason="draft_already_pending")
    elif status in FLAG:
        result.update(decision="flag", reason=status)
    else:
        result.update(decision="flag", reason="unknown_status")
    return result


def main() -> int:
    load_env()
    p = argparse.ArgumentParser(description="check.md contact-history gate")
    p.add_argument("email")
    p.add_argument("--domain")
    args = p.parse_args()
    print(json.dumps(check_email(Supabase(), args.email, args.domain), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

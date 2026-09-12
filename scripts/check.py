#!/usr/bin/env python3
"""check.md — one email in, a decision out. No APIs, no AI.

Same function for find.py survivors and a one-off manual lookup.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ENV_PATHS = (
    Path("/root/.hermes/.env"),
    Path("/root/hermes/.env"),
)

HARD_STOP_STATUSES = {
    "unsubscribed": "unsubscribed",
    "do_not_contact": "do_not_contact",
    "replied": "replied",
}
FLAG_STATUSES = frozenset({"contacted", "skipped"})
CLEAR_STATUSES = frozenset({"new"})
CONTACT_FIELDS = "status,unsubscribed_at,last_contacted_at,contact_count,notes,domain,email"
SSL_CTX = ssl.create_default_context()


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip("'").strip('"')


def _headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SECRET_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }


def _get(path_qs: str) -> list[dict[str, Any]]:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path_qs
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else []


def domain_from_email(email: str) -> str | None:
    if "@" not in email:
        return None
    host = email.rsplit("@", 1)[-1].strip().lower()
    return host or None


def check_email(candidate_email: str, candidate_domain: str | None = None) -> dict[str, Any]:
    """Return a consumable decision dict for one email."""
    email = (candidate_email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("candidate_email must be a single email address")

    qs = urllib.parse.urlencode(
        {
            "email": f"eq.{email}",
            "select": CONTACT_FIELDS,
            "limit": "1",
        }
    )
    rows = _get(f"contacts?{qs}")
    row = rows[0] if rows else None
    domain = (candidate_domain or (row or {}).get("domain") or domain_from_email(email) or "").strip().lower() or None

    others: list[dict[str, Any]] = []
    if domain:
        oqs = urllib.parse.urlencode(
            {
                "domain": f"eq.{domain}",
                "email": f"neq.{email}",
                "select": "email,status",
            }
        )
        others = _get(f"contacts?{oqs}")
    unsub_others = [o for o in others if o.get("status") == "unsubscribed"]
    domain_context = {
        "domain": domain,
        "other_contacts": len(others),
        "other_unsubscribed": len(unsub_others),
        "caution": (
            f"{len(others)} other contact(s) at this domain, {len(unsub_others)} unsubscribed."
            if others
            else None
        ),
    }

    result: dict[str, Any] = {
        "email": email,
        "decision": None,
        "reason": None,
        "status": None,
        "unsubscribed_at": None,
        "last_contacted_at": None,
        "contact_count": None,
        "notes": None,
        "domain": domain,
        "domain_context": domain_context,
        "row_found": bool(row),
    }

    if row is None:
        result["decision"] = "clear"
        result["reason"] = "first_touch"
        return result

    status = (row.get("status") or "").strip()
    result.update(
        {
            "status": status,
            "unsubscribed_at": row.get("unsubscribed_at"),
            "last_contacted_at": row.get("last_contacted_at"),
            "contact_count": row.get("contact_count"),
            "notes": row.get("notes"),
            "domain": row.get("domain") or domain,
        }
    )

    if status in HARD_STOP_STATUSES:
        result["decision"] = "hard_stop"
        result["reason"] = HARD_STOP_STATUSES[status]
        return result
    if status in CLEAR_STATUSES:
        result["decision"] = "clear"
        result["reason"] = "find_queue"
        return result
    if status in FLAG_STATUSES:
        result["decision"] = "flag"
        result["reason"] = status
        return result

    result["decision"] = "flag"
    result["reason"] = "unknown_status"
    return result


def main() -> int:
    for path in ENV_PATHS:
        load_env(path)
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SECRET_KEY"):
        raise SystemExit("missing SUPABASE_URL / SUPABASE_SECRET_KEY")

    p = argparse.ArgumentParser(description="check.md contact-history gate")
    p.add_argument("email", help="single candidate email")
    p.add_argument("--domain", help="override domain for informational lookup")
    args = p.parse_args()
    print(json.dumps(check_email(args.email, args.domain), indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

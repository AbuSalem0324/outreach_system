#!/usr/bin/env python3
"""deliver.py: the end of research.md and draft.md.

send:   verify the address, insert the contact as `new` with the draft on
        the row, send the draft file to Telegram, record message_id.
reject: mark the company rejected_research with a reason.

Both update companies_seen so the company never resurfaces silently.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from check import check_email
from common import (
    SOURCE,
    UNSUB_URL,
    Supabase,
    Telegram,
    domain_from_email,
    draft_file,
    load_env,
    log,
    now_iso,
    slug,
    today_str,
)
from verify import verify_email


def company_row(db: Supabase, company_number: str) -> dict[str, Any]:
    rows = db.select("companies_seen", company_number=f"eq.{company_number}", limit="1")
    if not rows:
        raise SystemExit(f"no companies_seen row for {company_number}; ingest first")
    return rows[0]


def cmd_reject(db: Supabase, args: argparse.Namespace) -> int:
    company_row(db, args.company_number)
    db.set_outcome(args.company_number, "rejected_research", args.reason)
    print(json.dumps({"company_number": args.company_number, "outcome": "rejected_research", "reason": args.reason}))
    return 0


def cmd_send(db: Supabase, args: argparse.Namespace) -> int:
    email = args.email.strip().lower()
    company = company_row(db, args.company_number)
    body = Path(args.body_file).read_text(encoding="utf-8").rstrip() + "\n"
    unsub = UNSUB_URL.format(email=email)
    if unsub not in body:
        raise SystemExit(f"body is missing the pre-filled unsubscribe link: {unsub}")
    if "\u2014" in body or "\u2014" in args.subject:
        raise SystemExit("em dash found in draft; fix the copy")

    # Backstop: check.md again on the address actually chosen
    check = check_email(db, email, company.get("domain"))
    if check["decision"] == "hard_stop":
        db.set_outcome(args.company_number, "rejected_check", f"{email}: {check['reason']}")
        print(json.dumps({"delivered": False, "why": "hard_stop", "check": check}, indent=2))
        return 3
    if check["decision"] == "clear" and check.get("reason") == "draft_already_pending":
        print(json.dumps({"delivered": False, "why": "draft_already_pending", "check": check}, indent=2))
        return 3

    if db.quota_remaining() <= 0 and not args.force:
        print(json.dumps({"delivered": False, "why": "quota_used_today"}, indent=2))
        return 4

    # verify.md
    v = verify_email(email) if not args.skip_verify else {"decision": "proceed", "reason": "skipped", "result": "ok"}
    if v["decision"] == "hold":
        db.set_outcome(args.company_number, "held_verify", f"{email}: {v['reason']}")
        print(json.dumps({"delivered": False, "why": "held_verify", "verify": v}, indent=2))
        return 5
    if v["decision"] == "drop":
        db.set_outcome(args.company_number, "rejected_verify", f"{email}: {v['reason']}")
        print(json.dumps({"delivered": False, "why": "rejected_verify", "verify": v}, indent=2))
        return 5

    notes = f"{today_str()} first touch. buyer={args.buyer_name or 'role-addressed'} ({args.buyer_role or '-'}). angle={args.angle}"
    contact = {
        "email": email,
        "company_name": company.get("company_name") or args.company_name,
        "domain": company.get("domain") or domain_from_email(email),
        "company_number": args.company_number,
        "sic_code": company.get("sic_code"),
        "campaign_id": company.get("campaign_id"),
        "icp_id": company.get("icp_id"),
        "source": SOURCE,
        "status": "new",
        "buyer_name": args.buyer_name or None,
        "buyer_role": args.buyer_role or None,
        "angle": args.angle,
        "notes": notes,
        "draft_subject": args.subject,
        "draft_body": body,
        "email_verification_status": v.get("result") or "ok",
    }
    row = db.insert("contacts", contact)[0]

    tg = Telegram()
    filename = f"{today_str()}_{slug(contact['company_name'])}.txt"
    caption = f"{contact['company_name']} · {args.buyer_role or 'role inbox'} · 👍 sent / 👎 skip"
    message_id = tg.send_document(filename, draft_file(email, args.subject, body), caption)
    db.patch("contacts", {"id": f"eq.{row['id']}"}, {"telegram_message_id": message_id, "draft_delivered_at": now_iso()})
    db.set_outcome(args.company_number, "promoted_to_contacts", f"{email} → contacts {row['id']}")
    log("deliver=sent", contact_id=row["id"], message_id=message_id, file=filename)
    print(json.dumps({"delivered": True, "contact_id": row["id"], "telegram_message_id": message_id, "file": filename}, indent=2))
    return 0


def main() -> int:
    load_env()
    p = argparse.ArgumentParser(description="deliver.py: send a draft or reject a company")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send")
    s.add_argument("--company-number", required=True)
    s.add_argument("--email", required=True)
    s.add_argument("--buyer-name", default="")
    s.add_argument("--buyer-role", default="")
    s.add_argument("--angle", required=True, help="one complete sentence; follow-ups reuse it verbatim")
    s.add_argument("--subject", required=True)
    s.add_argument("--body-file", required=True)
    s.add_argument("--company-name", help="fallback if companies_seen has none")
    s.add_argument("--skip-verify", action="store_true", help="tests only")
    s.add_argument("--force", action="store_true", help="ignore the daily cap; tests only")

    r = sub.add_parser("reject")
    r.add_argument("--company-number", required=True)
    r.add_argument("--reason", required=True)

    args = p.parse_args()
    db = Supabase()
    return cmd_send(db, args) if args.cmd == "send" else cmd_reject(db, args)


if __name__ == "__main__":
    sys.exit(main())

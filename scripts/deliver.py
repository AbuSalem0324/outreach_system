#!/usr/bin/env python3
"""deliver.py: the end of research-card.md.

send:   build the first touch from fixed copy plus the one generated
        sentence, verify the address, insert the contact as `new` with the
        draft on the row, send the draft file to Telegram, record message_id.
reject: mark the company rejected_research with a reason.
hold:   park the company for Adam with one question (held_review).
requeue: put a company back to pending. Adam's call, not research's.

reject and hold only work on the company next.py has handed out, so a
run cannot clear rows it was never given.

Both update companies_seen so the company never resurfaces silently.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from check import check_email
from common import (
    SOURCE,
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
from first_touch import build, check_sentence
from verify import verify_email


PHONE_TYPES = {"direct", "mobile", "switchboard"}


def enrichment_fields(linkedin_url: str, phone: str, phone_type: str, postal_address: str, now: str) -> dict[str, Any]:
    linkedin = (linkedin_url or "").strip() or None
    phone_v = (phone or "").strip() or None
    kind = (phone_type or "").strip() or None
    postal = (postal_address or "").strip() or None
    if phone_v and kind not in PHONE_TYPES:
        raise SystemExit("phone_type must be direct, mobile, or switchboard when phone is set")
    if kind and not phone_v:
        raise SystemExit("phone_type without phone")
    fields: dict[str, Any] = {
        "linkedin_url": linkedin,
        "phone": phone_v,
        "phone_type": kind,
        "postal_address": postal,
        "enrichment_source": None,
        "enriched_at": None,
    }
    if linkedin or phone_v:
        fields["enrichment_source"] = "hunter"
        fields["enriched_at"] = now
    return fields


def company_row(db: Supabase, company_number: str) -> dict[str, Any]:
    rows = db.select("companies_seen", company_number=f"eq.{company_number}", limit="1")
    if not rows:
        raise SystemExit(f"no companies_seen row for {company_number}; ingest first")
    return rows[0]


NEXT_CMD = "python3 scripts/next.py"
SENDABLE = {"in_research", "awaiting_pick", "held_verify", "held_review"}


def require_in_hand(company: dict[str, Any], verb: str) -> None:
    if company.get("outcome") != "in_research":
        log("guardrail=not_in_hand", verb=verb, company_number=company.get("company_number"), outcome=company.get("outcome"))
        raise SystemExit(
            f"{verb} refused: {company.get('company_number')} is not the company in hand "
            f"(outcome={company.get('outcome')}). Only the company next.py gave you can be finished."
        )


def decline(db: Supabase, args: argparse.Namespace, verb: str, outcome: str, text: str) -> int:
    text = (text or "").strip()
    if len(text) < 12:
        raise SystemExit(f"{verb} needs a specific sentence: what you saw, or what you need Adam to decide")
    require_in_hand(company_row(db, args.company_number), verb)
    db.set_outcome(args.company_number, outcome, text)
    print(json.dumps({"company_number": args.company_number, "outcome": outcome, "reason": text, "next": NEXT_CMD}))
    return 0


def cmd_reject(db: Supabase, args: argparse.Namespace) -> int:
    return decline(db, args, "reject", "rejected_research", args.reason)


def cmd_hold(db: Supabase, args: argparse.Namespace) -> int:
    return decline(db, args, "hold", "held_review", args.question)


def cmd_requeue(db: Supabase, args: argparse.Namespace) -> int:
    company = company_row(db, args.company_number)
    if company.get("outcome") == "promoted_to_contacts":
        raise SystemExit("already a contact; nothing to requeue")
    db.set_outcome(args.company_number, "pending", f"requeued from {company.get('outcome')}")
    print(json.dumps({"company_number": args.company_number, "outcome": "pending"}))
    return 0


def cmd_send(db: Supabase, args: argparse.Namespace) -> int:
    email = args.email.strip().lower()
    company = company_row(db, args.company_number)
    was = company.get("outcome")
    if was not in SENDABLE:
        log("guardrail=not_in_hand", verb="send", company_number=args.company_number, outcome=was)
        raise SystemExit(f"send refused: {args.company_number} has outcome={was}; it was not handed out by next.py or a picker")
    follow_on = {"next": NEXT_CMD} if was == "in_research" else {}
    if not company.get("website"):
        log("guardrail=send_without_site", company_number=args.company_number)
        raise SystemExit(
            "send refused: no website on record for this company. Find it and run "
            "site_lookup.py set, or finish with site_lookup.py none (card section 0)."
        )
    angle = check_sentence("--angle", args.angle)
    subject, body = build(company.get("icp_id"), email, args.buyer_name, args.relevance)

    # Backstop: check.md again on the address actually chosen
    check = check_email(db, email, company.get("domain"))
    if check["decision"] == "hard_stop":
        db.set_outcome(args.company_number, "rejected_check", f"{email}: {check['reason']}")
        print(json.dumps({"delivered": False, "why": "hard_stop", "check": check, **follow_on}, indent=2))
        return 3
    if check["decision"] == "clear" and check.get("reason") == "draft_already_pending":
        if was == "in_research":
            # Give it an outcome, or next.py would hand the same company out forever.
            db.set_outcome(args.company_number, "rejected_check", f"{email}: draft_already_pending")
        print(json.dumps({"delivered": False, "why": "draft_already_pending", "check": check, **follow_on}, indent=2))
        return 3

    # verify.md
    v = verify_email(email) if not args.skip_verify else {"decision": "proceed", "reason": "skipped", "result": "ok"}
    if v["decision"] == "hold":
        db.set_outcome(args.company_number, "held_verify", f"{email}: {v['reason']}")
        print(json.dumps({"delivered": False, "why": "held_verify", "verify": v, **follow_on}, indent=2))
        return 5
    if v["decision"] == "drop":
        db.set_outcome(args.company_number, "rejected_verify", f"{email}: {v['reason']}")
        print(json.dumps({"delivered": False, "why": "rejected_verify", "verify": v, **follow_on}, indent=2))
        return 5

    notes = f"{today_str()} first touch. buyer={args.buyer_name or 'role-addressed'} ({args.buyer_role or '-'}). angle={angle}"
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
        "angle": angle,
        "notes": notes,
        "draft_subject": subject,
        "draft_body": body,
        "email_verification_status": v.get("result") or "ok",
        **enrichment_fields(args.linkedin_url, args.phone, args.phone_type, args.postal_address, now_iso()),
    }
    row = db.insert("contacts", contact)[0]

    tg = Telegram()
    filename = f"{today_str()}_{slug(contact['company_name'])}.txt"
    site_record = (company.get("raw") or {}).get("_site") or {}
    unsure = f" · ⚠ site not matched by script: {site_record.get('url')}" if site_record.get("grade") == "unverified" else ""
    caption = f"{contact['company_name']} · {args.buyer_role or 'role inbox'}{unsure} · 👍 sent / 👎 skip"
    message_id = tg.send_document(filename, draft_file(email, subject, body), caption)
    db.patch("contacts", {"id": f"eq.{row['id']}"}, {"telegram_message_id": message_id, "draft_delivered_at": now_iso()})
    db.set_outcome(args.company_number, "promoted_to_contacts", f"{email} → contacts {row['id']}")
    log("deliver=sent", contact_id=row["id"], message_id=message_id, file=filename)
    print(json.dumps({"delivered": True, "contact_id": row["id"], "telegram_message_id": message_id, "file": filename, **follow_on}, indent=2))
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
    s.add_argument("--relevance", required=True, help="the one generated sentence of the first email")
    s.add_argument("--linkedin-url", default="")
    s.add_argument("--phone", default="")
    s.add_argument("--phone-type", default="")
    s.add_argument("--postal-address", default="")
    s.add_argument("--company-name", help="fallback if companies_seen has none")
    s.add_argument("--skip-verify", action="store_true", help="tests only")
    s.add_argument("--force", action="store_true", help="ignored; no daily cap")

    r = sub.add_parser("reject")
    r.add_argument("--company-number", required=True)
    r.add_argument("--reason", required=True)

    h = sub.add_parser("hold")
    h.add_argument("--company-number", required=True)
    h.add_argument("--question", required=True, help="the one thing Adam needs to decide")

    q = sub.add_parser("requeue")
    q.add_argument("--company-number", required=True)

    args = p.parse_args()
    db = Supabase()
    return {"send": cmd_send, "reject": cmd_reject, "hold": cmd_hold, "requeue": cmd_requeue}[args.cmd](db, args)


if __name__ == "__main__":
    sys.exit(main())

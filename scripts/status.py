#!/usr/bin/env python3
"""Manual status flips and the /status summary.

replied | dnc | unsub | close  <email>
summary
"""

from __future__ import annotations

import argparse
import json
import sys

from common import Supabase, load_env, now_iso
from followups import due_contacts

VERBS = {
    "replied": {"status": "replied"},
    "dnc": {"status": "do_not_contact"},
    "unsub": {"status": "unsubscribed"},
    "close": {"status": "closed"},
}


def flip(db: Supabase, verb: str, email: str) -> dict:
    email = email.strip().lower()
    row = db.contact_by_email(email)
    if not row:
        # Unsub and dnc still need a row so the address is blocked next time
        if verb in {"unsub", "dnc"}:
            payload = {"email": email, "source": "manual", **VERBS[verb]}
            if verb == "unsub":
                payload["unsubscribed_at"] = now_iso()
            return db.insert("contacts", payload)[0]
        raise SystemExit(f"no contact with email {email}")
    payload = {**VERBS[verb], "draft_subject": None, "draft_body": None, "telegram_message_id": None}
    if verb == "unsub":
        payload["unsubscribed_at"] = now_iso()
    return db.patch("contacts", {"email": f"eq.{email}"}, payload)[0]


def pending_tasks(db: Supabase) -> list[dict]:
    rows = db.select("messages", outcome="eq.pending", select="channel,sequence_step,telegram_message_id,contact_id")
    if not rows:
        return []
    ids = [r["contact_id"] for r in rows if r.get("contact_id")]
    found = db.select("contacts", id=f"in.({','.join(ids)})", select="id,email,company_name") if ids else []
    who = {c["id"]: c for c in found}
    out = []
    for row in rows:
        contact = who.get(row.get("contact_id"), {})
        out.append({
            "channel": row.get("channel"),
            "sequence_step": row.get("sequence_step"),
            "telegram_message_id": row.get("telegram_message_id"),
            "email": contact.get("email"),
            "company_name": contact.get("company_name"),
        })
    return out


def summary(db: Supabase) -> dict:
    used = db.first_touches_today()
    pending_first = db.select("contacts", status="eq.new", select="email,company_name,draft_delivered_at")
    pending_follow = db.select("contacts", status="eq.contacted", draft_subject="not.is.null", select="email,company_name,contact_count,draft_delivered_at")
    due = due_contacts(db)
    open_seq = db.select("contacts", status="eq.contacted", next_due_at="not.is.null", select="email")
    by_status = {}
    for r in db.select("contacts", select="status"):
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {
        "first_touches_today": used,
        "daily_cap": None,
        "drafts_awaiting_reaction": {"first_touch": pending_first, "follow_up": pending_follow},
        "pending_tasks": pending_tasks(db),
        "followups_due": due,
        "open_sequences": len(open_seq),
        "contacts_by_status": by_status,
    }


def main() -> int:
    load_env()
    p = argparse.ArgumentParser()
    p.add_argument("verb", choices=[*VERBS, "summary"])
    p.add_argument("email", nargs="?")
    args = p.parse_args()
    db = Supabase()
    if args.verb == "summary":
        print(json.dumps(summary(db), indent=2, default=str))
        return 0
    if not args.email:
        p.error("email required")
    row = flip(db, args.verb, args.email)
    print(json.dumps({"email": row["email"], "status": row["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

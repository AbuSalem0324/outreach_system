#!/usr/bin/env python3
"""/followups: build and deliver due follow-ups. Templated, no AI.

Due: status = contacted, next_due_at <= now(), no draft pending.
Touch number is contact_count + 1. Only 2 and 3 exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from common import (
    UNSUB_URL,
    Supabase,
    Telegram,
    draft_file,
    first_name,
    load_env,
    log,
    now_iso,
    slug,
    today_str,
)

SUBJECT_BY_ICP = {
    "home-turf-fmcg-v1": "Re: Forecasting and reporting for food manufacturers",
    "generalist-control-v1": "Re: Forecasting and reporting for SMEs",
}
DEFAULT_SUBJECT = SUBJECT_BY_ICP["home-turf-fmcg-v1"]

TOUCH_2 = """{greeting}

Following up on my note from earlier in the week. The short version:
{angle}

Happy to do a short call if that's useful, or I can send over a
one-page example of the kind of output I mean.

Adam

Not relevant? Let me know.
{unsub}
"""

TOUCH_3 = """{greeting}

Last one from me. If forecasting or reporting comes up at {company}
at some point, I'm easy to find, and the thinking behind my earlier
note still stands: {angle}

Adam

Not relevant? Let me know.
{unsub}
"""

TEMPLATES = {2: TOUCH_2, 3: TOUCH_3}


def build(contact: dict[str, Any], step: int) -> tuple[str, str]:
    name = first_name(contact.get("buyer_name"))
    greeting = f"Hi {name}," if name else "Hi,"
    angle = (contact.get("angle") or "").strip()
    if not angle:
        raise ValueError("contact has no angle; cannot template a follow-up")
    body = TEMPLATES[step].format(
        greeting=greeting,
        angle=angle,
        company=contact.get("company_name") or "your company",
        unsub=UNSUB_URL.format(email=contact["email"]),
    )
    subject = SUBJECT_BY_ICP.get(contact.get("icp_id") or "", DEFAULT_SUBJECT)
    return subject, body


def due_contacts(db: Supabase) -> list[dict[str, Any]]:
    return db.select(
        "contacts",
        status="eq.contacted",
        next_due_at=f"lte.{now_iso()}",
        draft_subject="is.null",
        contact_count="in.(1,2)",
        order="next_due_at.asc",
        select="id,email,company_name,buyer_name,buyer_role,angle,contact_count,last_contacted_at,next_due_at,icp_id",
    )


def run(args: argparse.Namespace) -> int:
    load_env()
    db = Supabase()
    due = due_contacts(db)
    if args.list or not due:
        print(json.dumps({"due": len(due), "contacts": [
            {k: c.get(k) for k in ("email", "company_name", "contact_count", "next_due_at")} for c in due
        ]}, indent=2))
        return 0

    tg = Telegram()
    delivered = []
    for c in due:
        step = int(c["contact_count"]) + 1
        try:
            subject, body = build(c, step)
        except ValueError as exc:
            log("followup=skip", email=c["email"], reason=str(exc))
            continue
        filename = f"{today_str()}_followup{step}_{slug(c.get('company_name'))}.txt"
        caption = f"{c.get('company_name')} · follow-up {step} of 3 · 👍 sent / 👎 close"
        message_id = tg.send_document(filename, draft_file(c["email"], subject, body), caption)
        db.patch(
            "contacts",
            {"id": f"eq.{c['id']}"},
            {
                "draft_subject": subject,
                "draft_body": body,
                "telegram_message_id": message_id,
                "draft_delivered_at": now_iso(),
            },
        )
        delivered.append({"email": c["email"], "step": step, "telegram_message_id": message_id})
        log("followup=delivered", email=c["email"], step=step, message_id=message_id)

    print(json.dumps({"due": len(due), "delivered": delivered}, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="/followups: templated touch 2 and 3")
    p.add_argument("--list", action="store_true", help="list due contacts, send nothing")
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())

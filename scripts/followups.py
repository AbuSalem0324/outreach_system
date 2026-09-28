#!/usr/bin/env python3
"""/followups: touches 2 to 4. Templated, no AI, nothing sends itself.

Due: status = contacted, next_due_at <= now(), no draft pending, no
pending messages row, contact_count in (1, 2, 3).
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

That is the kind of job I build around: a small forecasting or
reporting tool fitted to the current workflow, not another platform
to learn, and cheaper than an enterprise system most of which would
sit unused.

Happy to do a short call if that's useful, or I can send over a
one-page example of the kind of output I mean.

Adam

Not relevant? Let me know.
{unsub}
"""

TOUCH_3 = """{greeting}

One more note on this. If forecasting or reporting comes up at
{company} at some point, I'm easy to find. Still the same offer: a
tool built for how the work already runs, not a bloated system to
learn. The thinking behind my earlier note still stands: {angle}

Adam

Not relevant? Let me know.
{unsub}
"""

TEMPLATES = {2: TOUCH_2, 3: TOUCH_3}

WHO = """DataBard builds bespoke forecasting, reporting and small automation
tools for food manufacturers. Fixed scope, a working output, not a
six-month software programme. I spent years on the floor at Tesco
and on the service desk at 2 Sisters, so the work is aimed at how a
factory actually runs."""

DUE_SELECT = (
    "id,email,company_name,buyer_name,buyer_role,angle,contact_count,"
    "last_contacted_at,next_due_at,icp_id,linkedin_url,phone,phone_type,postal_address"
)
TASK_SUBJECT = {"linkedin": "LinkedIn connection", "letter": "Letter", "call": "Call"}


def route(contact: dict[str, Any], messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """What /followups should post. Does not send."""
    rows = messages or []
    if any(m.get("outcome") == "pending" for m in rows):
        return []
    count = int(contact["contact_count"])
    if count in (1, 2):
        step = count + 1
        actions = [{"kind": "email", "step": step}]
        if step == 3 and contact.get("linkedin_url") and not any(m.get("channel") == "linkedin" for m in rows):
            actions.append({"kind": "linkedin", "step": 3})
        return actions
    if count != 3:
        return []
    letters = [m for m in rows if m.get("channel") == "letter" and m.get("sequence_step") == 4]
    phones = [m for m in rows if m.get("channel") == "phone"]
    if not letters:
        if contact.get("postal_address"):
            return [{"kind": "letter", "step": 4}]
        if contact.get("phone"):
            return [{"kind": "call", "step": 4}]
        return [{"kind": "close", "step": 4}]
    if any(m.get("outcome") in ("done", "skipped") for m in letters):
        if phones:
            return []
        if contact.get("phone"):
            return [{"kind": "call", "step": 4}]
        return [{"kind": "close", "step": 4}]
    return []


def _greeting(contact: dict[str, Any]) -> str:
    name = first_name(contact.get("buyer_name"))
    return f"Hi {name}," if name else "Hi,"


def _angle(contact: dict[str, Any]) -> str:
    angle = (contact.get("angle") or "").strip()
    if not angle:
        raise ValueError("contact has no angle; cannot template a follow-up")
    return angle


def _refuse(text: str) -> str:
    if "\u2014" in text:
        raise ValueError("em dash in task body")
    return text


def build(contact: dict[str, Any], step: int) -> tuple[str, str]:
    body = TEMPLATES[step].format(
        greeting=_greeting(contact),
        angle=_angle(contact),
        company=contact.get("company_name") or "your company",
        unsub=UNSUB_URL.format(email=contact["email"]),
    )
    subject = SUBJECT_BY_ICP.get(contact.get("icp_id") or "", DEFAULT_SUBJECT)
    return subject, body


def letter_text(contact: dict[str, Any]) -> str:
    name = contact.get("buyer_name") or contact.get("buyer_role") or ""
    role = contact.get("buyer_role") or ""
    company = contact.get("company_name") or ""
    unsub = UNSUB_URL.format(email=contact["email"])
    text = (
        f"{name}\n{role}\n{company}\n{contact.get('postal_address') or ''}\n\n"
        f"{_greeting(contact)}\n\n{WHO}\n\n{_angle(contact)}\n\n"
        "Happy to do a short call if that's useful.\n\nAdam\n\n"
        "If you'd rather I didn't write again, let me know.\n"
        f"{unsub}\n"
    )
    if unsub not in text:
        raise ValueError("letter is missing the unsubscribe link")
    return _refuse(text)


def call_text(contact: dict[str, Any]) -> str:
    name = contact.get("buyer_name") or "Unknown"
    role = contact.get("buyer_role") or "unknown role"
    lines = [
        f"Call: {contact.get('company_name') or 'unknown company'}",
        f"{name}, {role}",
        f"{contact.get('phone') or ''} ({contact.get('phone_type') or 'unclear'})",
        "",
        f"Prompt: {_angle(contact)}",
        "",
        "Check Corporate TPS before calling.",
    ]
    if contact.get("phone_type") == "mobile":
        lines.append("Check TPS as well. This number may be personal.")
    lines.extend(["", "👍 called / 👎 not calling / 🤝 we spoke"])
    return _refuse("\n".join(lines) + "\n")


def linkedin_text(contact: dict[str, Any]) -> str:
    name = contact.get("buyer_name") or "Unknown"
    role = contact.get("buyer_role") or "unknown role"
    text = (
        "LinkedIn: connection request only. No pitch in the note.\n\n"
        f"{name}\n{role}\n{contact.get('company_name') or ''}\n"
        f"{contact.get('linkedin_url') or ''}\n\n"
        "👍 sent / 👎 not sending / 🤝 they responded\n"
    )
    return _refuse(text)


def pending_contact_ids(db: Supabase) -> set[str]:
    rows = db.select("messages", outcome="eq.pending", select="contact_id")
    return {r["contact_id"] for r in rows if r.get("contact_id")}


def due_contacts(db: Supabase) -> list[dict[str, Any]]:
    rows = db.select(
        "contacts",
        status="eq.contacted",
        next_due_at=f"lte.{now_iso()}",
        draft_subject="is.null",
        contact_count="in.(1,2,3)",
        order="next_due_at.asc",
        select=DUE_SELECT,
    )
    pending = pending_contact_ids(db)
    return [r for r in rows if r["id"] not in pending]


def messages_by_contact(db: Supabase, ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {i: [] for i in ids}
    if not ids:
        return grouped
    rows = db.select(
        "messages",
        contact_id=f"in.({','.join(ids)})",
        select="contact_id,channel,sequence_step,outcome",
    )
    for row in rows:
        grouped.setdefault(row["contact_id"], []).append(row)
    return grouped


def linkedin_gaps(db: Supabase) -> list[dict[str, Any]]:
    """Touch 3 email already drafted, LinkedIn task never inserted."""
    rows = db.select(
        "contacts",
        status="eq.contacted",
        contact_count="eq.2",
        linkedin_url="not.is.null",
        draft_subject="not.is.null",
        select=DUE_SELECT,
    )
    if not rows:
        return []
    existing = messages_by_contact(db, [r["id"] for r in rows])
    return [r for r in rows if not any(m.get("channel") == "linkedin" for m in existing.get(r["id"], []))]


def _summary(contact: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "email": contact.get("email"),
        "company_name": contact.get("company_name"),
        "contact_count": contact.get("contact_count"),
        "next_due_at": contact.get("next_due_at"),
        "actions": actions,
    }


def post_task(db: Supabase, tg: Telegram, contact: dict[str, Any], kind: str, step: int, body: str, *, filename: str | None = None, caption: str | None = None) -> dict[str, Any]:
    if kind == "letter":
        message_id = tg.send_document(filename or "letter.txt", body, caption)
    else:
        message_id = tg.send_text(body)
    record = {
        "email": contact["email"],
        "kind": kind,
        "step": step,
        "telegram_message_id": message_id,
    }
    try:
        db.insert(
            "messages",
            {
                "contact_id": contact["id"],
                "direction": "outbound",
                "channel": kind,
                "sequence_step": step,
                "subject": TASK_SUBJECT[kind],
                "body": body,
                "outcome": "pending",
                "telegram_message_id": message_id,
            },
        )
    except Exception as exc:  # noqa: BLE001
        log("followup=task_insert_failed", email=contact["email"], kind=kind, message_id=message_id, reason=str(exc))
        record["task_insert_failed"] = str(exc)
        return record
    log("followup=task", email=contact["email"], kind=kind, step=step, message_id=message_id)
    return record


def deliver_actions(db: Supabase, tg: Telegram, contact: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    done: list[dict[str, Any]] = []
    for action in actions:
        kind = action["kind"]
        step = action["step"]
        if kind == "email":
            subject, body = build(contact, step)
            filename = f"{today_str()}_followup{step}_{slug(contact.get('company_name'))}.txt"
            caption = f"{contact.get('company_name')} · follow-up {step} of 4 · 👍 sent / 👎 close"
            message_id = tg.send_document(filename, draft_file(contact["email"], subject, body), caption)
            db.patch(
                "contacts",
                {"id": f"eq.{contact['id']}"},
                {
                    "draft_subject": subject,
                    "draft_body": body,
                    "telegram_message_id": message_id,
                    "draft_delivered_at": now_iso(),
                },
            )
            done.append({"email": contact["email"], "kind": "email", "step": step, "telegram_message_id": message_id})
            log("followup=delivered", email=contact["email"], step=step, message_id=message_id)
            continue
        if kind == "linkedin":
            done.append(post_task(db, tg, contact, "linkedin", step, linkedin_text(contact)))
            if done[-1].get("task_insert_failed"):
                break
            continue
        if kind == "letter":
            filename = f"{today_str()}_letter_{slug(contact.get('company_name'))}.txt"
            caption = "Printed envelope, stamp, no window. 👍 posted / 👎 no letter, call next / 🤝 they responded"
            done.append(post_task(db, tg, contact, "letter", step, letter_text(contact), filename=filename, caption=caption))
            if done[-1].get("task_insert_failed"):
                break
            continue
        if kind == "call":
            done.append(post_task(db, tg, contact, "phone", step, call_text(contact)))
            if done[-1].get("task_insert_failed"):
                break
            continue
        if kind == "close":
            db.patch(
                "contacts",
                {"id": f"eq.{contact['id']}"},
                {"status": "closed", "draft_subject": None, "draft_body": None, "telegram_message_id": None},
            )
            done.append({"email": contact["email"], "kind": "close", "step": step})
            log("followup=closed", email=contact["email"], reason="nothing_left")
    return done


def run(args: argparse.Namespace) -> int:
    load_env()
    db = Supabase()
    due = due_contacts(db)
    grouped = messages_by_contact(db, [c["id"] for c in due])
    planned = [(c, route(c, grouped.get(c["id"], []))) for c in due]
    if args.list:
        print(json.dumps({"due": len(due), "contacts": [_summary(c, actions) for c, actions in planned]}, indent=2))
        return 0
    if not due and not linkedin_gaps(db):
        print(json.dumps({"due": 0, "delivered": []}, indent=2))
        return 0

    tg = Telegram()
    delivered: list[dict[str, Any]] = []
    for contact in linkedin_gaps(db):
        try:
            delivered.append(post_task(db, tg, contact, "linkedin", 3, linkedin_text(contact)))
        except ValueError as exc:
            log("followup=skip", email=contact["email"], reason=str(exc))
    for contact, actions in planned:
        if not actions:
            continue
        try:
            delivered.extend(deliver_actions(db, tg, contact, actions))
        except ValueError as exc:
            log("followup=skip", email=contact["email"], reason=str(exc))
    print(json.dumps({"due": len(due), "delivered": delivered}, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="/followups: templated touches 2 to 4")
    p.add_argument("--list", action="store_true", help="list due contacts, send nothing")
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())

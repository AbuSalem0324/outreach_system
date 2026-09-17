#!/usr/bin/env python3
"""send-and-log.md: turn a Telegram reaction into a database write.

Production path: Hermes plugin `send-and-log` on gateway_platform_event,
calling apply_decision(). The gateway already long-polls Telegram, so
this module must not poll while the gateway runs.

Standalone `python3 send_and_log_listener.py` is for isolated tests only.
Telegram allows one getUpdates client per bot; a second poller 409s.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
from typing import Any

from common import SOURCE, Supabase, http_json, load_env, log, require_env

SENT_EMOJI = "👍"
SKIP_EMOJI = "👎"
POLL_TIMEOUT_S = 50
BACKOFF_S = 5


def reaction_emojis(reactions: list[dict[str, Any]] | None) -> list[str]:
    return [r["emoji"] for r in reactions or [] if r.get("emoji")]


def contains(emojis: list[str], needle: str) -> bool:
    n = needle.replace("\ufe0f", "")
    return any(n in e.replace("\ufe0f", "") for e in emojis)


def apply_decision(db: Supabase, message_id: int, new_emojis: list[str], actor: str | None = None) -> None:
    try:
        rows = db.select(
            "contacts",
            telegram_message_id=f"eq.{message_id}",
            select="id,email,company_name,domain,status,notes,draft_subject,draft_body",
        )
    except Exception as exc:  # noqa: BLE001
        log("decision=error", message_id=message_id, reason=f"lookup_failed:{exc}")
        return
    if not rows:
        log("decision=ignore", message_id=message_id, reason="no_matching_row_or_already_processed")
        return

    sent = contains(new_emojis, SENT_EMOJI)
    skipped = contains(new_emojis, SKIP_EMOJI)

    for row in rows:
        status = row.get("status") or ""
        common = {"message_id": message_id, "contact_id": row["id"], "email": row["email"], "status": status, "actor": actor or "-"}
        clear = {"draft_subject": None, "draft_body": None, "telegram_message_id": None}

        try:
            if sent and status in {"new", "contacted"}:
                db.rpc(
                    "log_contact",
                    {
                        "p_email": row["email"],
                        "p_company_name": row.get("company_name"),
                        "p_domain": row.get("domain"),
                        "p_source": SOURCE,
                        "p_notes": None,
                        "p_subject": row.get("draft_subject"),
                        "p_body": row.get("draft_body"),
                        "p_telegram_message_id": message_id,
                    },
                )
                log("decision=log_contact", **common, action="touch_logged")
            elif skipped and status == "new":
                db.patch("contacts", {"id": f"eq.{row['id']}"}, {"status": "skipped", **clear})
                log("decision=skip", **common, action="status=skipped")
            elif skipped and status == "contacted":
                db.patch("contacts", {"id": f"eq.{row['id']}"}, {"status": "closed", **clear})
                log("decision=close", **common, action="status=closed")
            else:
                log("decision=ignore", **common, new_reaction=",".join(new_emojis) or "-", reason="unhandled")
        except Exception as exc:  # noqa: BLE001
            log("decision=error", **common, reason=str(exc))


def poll_forever(token: str, db: Supabase) -> None:
    api = f"https://api.telegram.org/bot{token}"
    offset = 0
    log("listener=start", mode="polling", allowed_updates="message_reaction")
    while True:
        params = {"timeout": POLL_TIMEOUT_S, "offset": offset, "allowed_updates": json.dumps(["message_reaction"])}
        status, payload = http_json(f"{api}/getUpdates?{urllib.parse.urlencode(params)}", timeout=POLL_TIMEOUT_S + 15)
        if status == 409:
            log("listener=conflict", reason="another_getUpdates_client", backoff_s=BACKOFF_S)
            time.sleep(BACKOFF_S)
            continue
        if status >= 300 or not (payload or {}).get("ok"):
            log("listener=poll_error", http=status, error=payload)
            time.sleep(BACKOFF_S)
            continue
        for update in payload.get("result") or []:
            offset = max(offset, int(update["update_id"]) + 1)
            event = update.get("message_reaction")
            if not event:
                continue
            user = event.get("user") or event.get("actor_chat") or {}
            actor = user.get("username") or user.get("id")
            new_emojis = reaction_emojis(event.get("new_reaction"))
            log("event=message_reaction", message_id=event["message_id"], actor=actor or "-", new_reaction=",".join(new_emojis) or "-")
            apply_decision(db, int(event["message_id"]), new_emojis, str(actor) if actor is not None else None)


def main() -> None:
    load_env()
    creds = require_env("TELEGRAM_BOT_TOKEN")
    db = Supabase()
    try:
        poll_forever(creds["TELEGRAM_BOT_TOKEN"], db)
    except KeyboardInterrupt:
        log("listener=stop")
        sys.exit(0)


if __name__ == "__main__":
    main()

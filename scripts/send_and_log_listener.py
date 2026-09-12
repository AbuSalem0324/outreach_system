#!/usr/bin/env python3
"""Send-and-log reaction handler.

Production path: Hermes plugin `send-and-log` (gateway_platform_event).
The gateway already long-polls Telegram; this module must not poll while
the gateway is running.

Standalone `python3 send_and_log_listener.py` is for isolated tests only.
Telegram allows one getUpdates client per bot — a second poller 409s.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SENT_EMOJI = "👍"
SKIP_EMOJI = "👎"
SOURCE = "find_pipeline"
POLL_TIMEOUT_S = 50
CONFLICT_BACKOFF_S = 5
ENV_PATHS = (
    Path("/root/.hermes/.env"),
    Path("/root/hermes/.env"),
)

# Later files win so /root/hermes/.env overrides Hermes-home values.
TERMINAL_STATUSES = frozenset({"contacted", "skipped"})


def log(msg: str, **fields: Any) -> None:
    if fields:
        extras = " ".join(f"{k}={v}" for k, v in fields.items())
        print(f"{msg} {extras}", flush=True)
    else:
        print(msg, flush=True)


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            os.environ[key] = value


def require_env(*names: str) -> dict[str, str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)}")
    return {n: os.environ[n] for n in names}


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> Any:
    body = None
    req_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {err_body}") from exc


def reaction_emojis(reactions: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []
    for item in reactions or []:
        if item.get("type") == "emoji" and item.get("emoji"):
            out.append(item["emoji"])
        elif item.get("emoji"):
            out.append(item["emoji"])
    return out


def contains_emoji(emojis: list[str], needle: str) -> bool:
    # 🗑️ may arrive with or without U+FE0F
    compact_needle = needle.replace("\ufe0f", "")
    for emoji in emojis:
        if needle in emoji or compact_needle in emoji.replace("\ufe0f", ""):
            return True
    return False


class Supabase:
    def __init__(self, url: str, key: str) -> None:
        self.base = url.rstrip("/")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }

    def contacts_by_telegram_message_id(self, message_id: int) -> list[dict[str, Any]]:
        qs = urllib.parse.urlencode(
            {
                "telegram_message_id": f"eq.{message_id}",
                "select": "id,email,company_name,domain,source,status,notes,telegram_message_id",
            }
        )
        data = http_json(
            f"{self.base}/rest/v1/contacts?{qs}",
            headers=self.headers,
            timeout=30,
        )
        return data or []

    def log_contact(self, contact: dict[str, Any]) -> Any:
        return http_json(
            f"{self.base}/rest/v1/rpc/log_contact",
            method="POST",
            payload={
                "p_email": contact["email"],
                "p_company_name": contact.get("company_name"),
                "p_domain": contact.get("domain"),
                "p_source": SOURCE,
                "p_notes": contact.get("notes"),
            },
            headers=self.headers,
            timeout=30,
        )

    def mark_skipped(self, contact_id: str) -> Any:
        headers = dict(self.headers)
        headers["Prefer"] = "return=representation"
        return http_json(
            f"{self.base}/rest/v1/contacts?id=eq.{urllib.parse.quote(contact_id)}",
            method="PATCH",
            payload={"status": "skipped"},
            headers=headers,
            timeout=30,
        )


def apply_decision(db: Supabase, message_id: int, new_emojis: list[str], actor: str | None) -> None:
    try:
        rows = db.contacts_by_telegram_message_id(message_id)
    except Exception as exc:
        log("decision=error", message_id=message_id, reason=f"lookup_failed:{exc}")
        return

    if not rows:
        log(
            "decision=ignore",
            message_id=message_id,
            actor=actor or "-",
            new_reaction=",".join(new_emojis) or "-",
            reason="no_matching_telegram_message_id",
        )
        return

    sent = contains_emoji(new_emojis, SENT_EMOJI)
    skipped = contains_emoji(new_emojis, SKIP_EMOJI)

    for row in rows:
        status = row.get("status") or ""
        email = row.get("email") or "-"
        common = {
            "message_id": message_id,
            "contact_id": row.get("id"),
            "email": email,
            "status": status,
            "actor": actor or "-",
            "new_reaction": ",".join(new_emojis) or "-",
        }

        if status in TERMINAL_STATUSES:
            log("decision=ignore", **common, reason="idempotency_guard")
            continue

        if sent and status == "new":
            try:
                db.log_contact(row)
                log("decision=log_contact", **common, action="status=contacted")
            except Exception as exc:
                log("decision=error", **common, reason=f"log_contact_failed:{exc}")
            continue

        if skipped and status == "new":
            try:
                db.mark_skipped(row["id"])
                log("decision=skip", **common, action="status=skipped")
            except Exception as exc:
                log("decision=error", **common, reason=f"skip_failed:{exc}")
            continue

        if sent or skipped:
            log("decision=ignore", **common, reason="row_not_new")
            continue

        log("decision=ignore", **common, reason="unhandled_reaction")


def poll_forever(token: str, db: Supabase) -> None:
    api = f"https://api.telegram.org/bot{token}"
    offset = 0
    log("listener=start", mode="polling", allowed_updates="message_reaction")
    while True:
        params = {
            "timeout": POLL_TIMEOUT_S,
            "offset": offset,
            "allowed_updates": json.dumps(["message_reaction"]),
        }
        url = f"{api}/getUpdates?{urllib.parse.urlencode(params)}"
        try:
            payload = http_json(url, timeout=POLL_TIMEOUT_S + 15)
        except RuntimeError as exc:
            text = str(exc)
            if "409" in text or "Conflict" in text:
                log(
                    "listener=conflict",
                    reason="another_getUpdates_client",
                    backoff_s=CONFLICT_BACKOFF_S,
                )
                time.sleep(CONFLICT_BACKOFF_S)
                continue
            log("listener=poll_error", error=text)
            time.sleep(CONFLICT_BACKOFF_S)
            continue
        except Exception as exc:
            log("listener=poll_error", error=exc)
            time.sleep(CONFLICT_BACKOFF_S)
            continue

        if not payload or not payload.get("ok"):
            log("listener=poll_error", error=payload)
            time.sleep(CONFLICT_BACKOFF_S)
            continue

        for update in payload.get("result") or []:
            update_id = int(update["update_id"])
            offset = max(offset, update_id + 1)
            event = update.get("message_reaction")
            if not event:
                log("decision=ignore", update_id=update_id, reason="not_message_reaction")
                continue

            message_id = int(event["message_id"])
            new_emojis = reaction_emojis(event.get("new_reaction"))
            old_emojis = reaction_emojis(event.get("old_reaction"))
            user = event.get("user") or event.get("actor_chat") or {}
            actor = user.get("username") or user.get("id")
            log(
                "event=message_reaction",
                message_id=message_id,
                actor=actor or "-",
                old_reaction=",".join(old_emojis) or "-",
                new_reaction=",".join(new_emojis) or "-",
            )
            apply_decision(db, message_id, new_emojis, str(actor) if actor is not None else None)


def main() -> None:
    for path in ENV_PATHS:
        load_env(path)
    creds = require_env("TELEGRAM_BOT_TOKEN", "SUPABASE_URL", "SUPABASE_SECRET_KEY")
    db = Supabase(creds["SUPABASE_URL"], creds["SUPABASE_SECRET_KEY"])
    try:
        poll_forever(creds["TELEGRAM_BOT_TOKEN"], db)
    except KeyboardInterrupt:
        log("listener=stop")
        sys.exit(0)


if __name__ == "__main__":
    main()

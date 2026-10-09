#!/usr/bin/env python3
"""Offer a recipient picker on Telegram. Does not choose or draft.

resolve prints the research card above the chosen recipient, so the
relevance sentence is written against the same rules as a straight send.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from common import Supabase, Telegram, load_env, log, now_iso, research_card

PICKS_DIR = Path("/root/outreach/picks")


def pick_path(company_number: str) -> Path:
    return PICKS_DIR / f"{company_number}.json"


def format_offer(payload: dict[str, Any]) -> str:
    name = payload.get("company_name") or payload.get("company_number")
    lines = [f"Email candidates — {name}", f"o/to {payload['company_number']} N   or   o/to {payload['company_number']} email", ""]
    for i, c in enumerate(payload.get("candidates") or [], start=1):
        kind = c.get("kind") or "personal"
        who = c.get("name") or kind
        role = c.get("position") or c.get("department") or kind
        conf = c.get("confidence")
        conf_s = f" (conf {conf})" if conf is not None else ""
        lines.append(f"{i}. {c.get('email')} — {who}, {role}{conf_s}")
        if c.get("reason"):
            lines.append(f"   -> {c['reason']}")
    lines.append("")
    lines.append("Reply o/to <company_number> <n or email>. No draft until you pick.")
    return "\n".join(lines)[:4000]


def cmd_offer(args: argparse.Namespace) -> int:
    load_env()
    path = Path(args.file) if args.file else pick_path(args.company_number)
    payload = json.loads(path.read_text(encoding="utf-8"))
    cn = payload.get("company_number") or args.company_number
    if not cn:
        raise SystemExit("company_number missing")
    payload["company_number"] = cn
    payload["offered_at"] = now_iso()
    PICKS_DIR.mkdir(parents=True, exist_ok=True)
    dest = pick_path(cn)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    text = format_offer(payload)
    tg = Telegram()
    message_id = tg.send_text(text)
    db = Supabase()
    db.set_outcome(cn, "awaiting_pick", "hunter picker; no To until o/to")
    log("pick=offered", company_number=cn, message_id=message_id, n=len(payload.get("candidates") or []))
    print(json.dumps({"offered": True, "company_number": cn, "telegram_message_id": message_id, "file": str(dest), "next": "python3 scripts/next.py"}, indent=2))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    path = pick_path(args.company_number)
    if not path.is_file():
        raise SystemExit(f"no pick file: {path}")
    print(path.read_text(encoding="utf-8"))
    return 0


def resolve_choice(payload: dict[str, Any], choice: str) -> dict[str, Any]:
    choice = choice.strip()
    cands = payload.get("candidates") or []
    if choice.isdigit():
        idx = int(choice)
        if idx < 1 or idx > len(cands):
            raise SystemExit(f"choice {idx} out of range 1..{len(cands)}")
        return cands[idx - 1]
    email = choice.lower()
    for c in cands:
        if (c.get("email") or "").lower() == email:
            return c
    raise SystemExit(f"email not in candidate list: {email}")


def chosen_payload(payload: dict[str, Any], chosen: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_number": payload.get("company_number"),
        "company_name": payload.get("company_name"),
        "angle": payload.get("angle"),
        "postal_address": payload.get("postal_address") or None,
        "buyer_name": chosen.get("name") or "",
        "buyer_role": chosen.get("position") or "",
        "chosen": {
            "email": chosen.get("email"),
            "name": chosen.get("name"),
            "position": chosen.get("position"),
            "linkedin_url": chosen.get("linkedin_url") or None,
            "phone": chosen.get("phone") or None,
            "phone_type": chosen.get("phone_type") or None,
        },
    }


def cmd_resolve(args: argparse.Namespace) -> int:
    path = pick_path(args.company_number)
    if not path.is_file():
        raise SystemExit(f"no pick file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    chosen = resolve_choice(payload, args.choice)
    if not args.no_card:
        print(research_card())
        print("===== CHOSEN (JSON) =====")
        print("Sections 1 to 4 are already decided for this company: use this email and this angle.")
        print("Write the relevance sentence (section 5), then deliver.py send.")
    print(json.dumps(chosen_payload(payload, chosen), indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Telegram recipient picker")
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("offer")
    o.add_argument("--company-number", required=True)
    o.add_argument("--file", help="JSON payload; default /root/outreach/picks/<cn>.json")
    s = sub.add_parser("show")
    s.add_argument("--company-number", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("--company-number", required=True)
    r.add_argument("choice", help="1-based index or email")
    r.add_argument("--no-card", action="store_true", help="JSON only")
    args = p.parse_args()
    if args.cmd == "offer":
        return cmd_offer(args)
    if args.cmd == "show":
        return cmd_show(args)
    return cmd_resolve(args)


if __name__ == "__main__":
    sys.exit(main())

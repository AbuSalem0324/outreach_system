#!/usr/bin/env python3
"""The /next run: one company at a time, counted in code.

A run is "deliver N drafts". Its definition lives in a small local file;
every count is derived from companies_seen, so nothing here can drift
from the database. Hermes never sees how many companies are left.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_DIR = Path(os.environ.get("OUTREACH_STATE_DIR", "/root/outreach"))
RUN_FILE = STATE_DIR / "run.json"
BUNDLES_DIR = STATE_DIR / "bundles"

# A run left alone this long is treated as abandoned: the next /next n
# starts fresh instead of topping up yesterday's.
RUN_IDLE_S = 3 * 60 * 60
# Consecutive research rejections or holds before the run stops and
# reports. Honest rejection rates on Endole exports run above half, so
# this is set to catch a model clearing the queue, not a bad patch.
MAX_REJECT_STREAK = int(os.environ.get("OUTREACH_MAX_REJECT_STREAK", "8"))

DELIVERED = "promoted_to_contacts"
MODEL_DECLINED = {"rejected_research", "held_review", "no_site_found"}
RUN_OUTCOMES = (
    DELIVERED, "awaiting_pick", "held_verify", "rejected_verify",
    "held_review", "rejected_research", "no_site_found", "rejected_check", "rejected_ingest",
)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_run() -> dict[str, Any] | None:
    if not RUN_FILE.is_file():
        return None
    try:
        return json.loads(RUN_FILE.read_text(encoding="utf-8"))
    except ValueError:
        return None


def save_run(run: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RUN_FILE.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")


def is_live(run: dict[str, Any] | None, now: datetime) -> bool:
    if not run or run.get("stopped"):
        return False
    return (now - _parse(run["touched_at"])).total_seconds() < RUN_IDLE_S


def decide_run(existing: dict[str, Any] | None, target: int, campaign_id: str, now: datetime) -> tuple[dict[str, Any], bool]:
    """--target n: continue a live run with the same target, else start one.

    Returns (run, started_new). Repeating --target mid-run must not reset
    the count, or the run would never reach its target.
    """
    if is_live(existing, now) and existing["target"] == target and existing["campaign_id"] == campaign_id:
        return existing, False
    stamp = now.isoformat()
    return {"campaign_id": campaign_id, "target": target, "started_at": stamp, "touched_at": stamp, "stopped": None}, True


def reject_streak(rows: list[dict[str, Any]]) -> int:
    """Trailing run of model rejections and holds. rows oldest first.

    Script-side skips (no website, check hard stop) are not the model's
    decision and are ignored. Anything that reached deliver.py send, or
    a picker, ends the streak.
    """
    n = 0
    for row in reversed(rows):
        outcome = row.get("outcome")
        if outcome in MODEL_DECLINED:
            n += 1
        elif outcome in ("rejected_check", "rejected_ingest"):
            continue
        else:
            break
    return n


def stop_reason(run: dict[str, Any], rows: list[dict[str, Any]]) -> str | None:
    if sum(1 for r in rows if r.get("outcome") == DELIVERED) >= run["target"]:
        return "target_reached"
    if reject_streak(rows) >= MAX_REJECT_STREAK:
        return "reject_streak"
    return None


def _named(rows: list[dict[str, Any]], outcome: str, key: str | None = None) -> list[Any]:
    out = []
    for r in rows:
        if r.get("outcome") != outcome:
            continue
        name = r.get("company_name") or r.get("company_number")
        out.append({"company": name, "company_number": r.get("company_number"), key: r.get("reason")} if key else name)
    return out


WHY = {
    "target_reached": "Target reached.",
    "reject_streak": f"Stopped early: {MAX_REJECT_STREAK} companies in a row were rejected, held, or had no site found. "
                     "Check the reasons below, then /next again to carry on.",
    "no_pending": "No pending companies left in this campaign.",
    "no_active_run": "No run in progress. Start one with: python3 scripts/next.py --target <n>",
}


def report(run: dict[str, Any] | None, rows: list[dict[str, Any]], why: str) -> dict[str, Any]:
    delivered = _named(rows, DELIVERED)
    return {
        "stop": True,
        "why": why,
        "summary": WHY[why],
        "target": run["target"] if run else None,
        "delivered": len(delivered),
        "delivered_companies": delivered,
        "awaiting_pick": _named(rows, "awaiting_pick"),
        "held_for_adam": _named(rows, "held_review", "question"),
        "held_verify": _named(rows, "held_verify", "reason"),
        "rejected_verify": _named(rows, "rejected_verify", "reason"),
        "rejected_research": _named(rows, "rejected_research", "reason"),
        "no_site_found": _named(rows, "no_site_found", "searched"),
        "skipped_by_script": sum(1 for r in rows if r.get("outcome") in ("rejected_check", "rejected_ingest")),
        "instruction": "Reply to Adam once with this report, including each rejection reason and each held "
                       "question. Do not call next.py again and do not research any other company.",
    }


def bundle_path(company_number: str) -> Path:
    return BUNDLES_DIR / f"{company_number}.json"


def cache_bundle(bundle: dict[str, Any]) -> None:
    BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
    bundle_path(bundle["company_number"]).write_text(json.dumps(bundle, ensure_ascii=False) + "\n", encoding="utf-8")


def cached_bundle(company_number: str) -> dict[str, Any] | None:
    path = bundle_path(company_number)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None

#!/usr/bin/env python3
"""verify.md: one email in, a deliverability decision out.

Pure decision. deliver.py is what acts on it; this script never writes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from typing import Any

from common import http_json, load_env

VERIFY_URL = "https://api.millionverifier.com/api/v3/"
CREDITS_URL = "https://api.millionverifier.com/api/v3/credits"
TIMEOUT_S = 10

DEMO_KEYS = {
    "ok": "API_KEY_FOR_OK",
    "invalid": "API_KEY_FOR_INVALID",
    "catch_all": "API_KEY_FOR_CATCH_ALL",
    "disposable": "API_KEY_FOR_DISPOSABLE",
    "unknown": "API_KEY_FOR_UNKOWN",  # MillionVerifier's own spelling
    "error": "API_KEY_FOR_ERROR_INSUFFICIENT_CREDITS",
}

DECISION = {
    "ok": "proceed",
    "catch_all": "hold",
    "unknown": "hold",
    "invalid": "drop",
    "disposable": "drop",
}


def mv_key() -> str:
    return os.environ.get("MILLIONVERIFIER_API_KEY") or os.environ.get("MILLIONVERIFIER_KEY") or ""


def millionverifier(email: str, api_key: str) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"api": api_key, "email": email, "timeout": TIMEOUT_S})
    status, data = http_json(VERIFY_URL + "?" + qs, timeout=TIMEOUT_S + 5)
    if not isinstance(data, dict):
        return {"error": f"non-json HTTP {status}", "result": "", "email": email}
    if status >= 300 and not data.get("error"):
        data["error"] = f"HTTP {status}"
    return data


def decide(payload: dict[str, Any]) -> dict[str, Any]:
    error = (payload.get("error") or "").strip()
    result = (payload.get("result") or "").strip().lower()
    out = {
        "email": payload.get("email"),
        "decision": None,
        "reason": None,
        "result": result or None,
        "subresult": payload.get("subresult") or None,
        "quality": payload.get("quality"),
        "free": payload.get("free"),
        "role": payload.get("role"),
        "didyoumean": payload.get("didyoumean") or None,
        "credits": payload.get("credits"),
        "error": error or None,
    }
    if error:
        out.update(decision="hold", reason=f"api_error: {error}", result=None)
    elif result not in DECISION:
        out.update(decision="hold", reason="unknown", result="unknown")
    else:
        out.update(decision=DECISION[result], reason=result)
    return out


def verify_email(email: str, api_key: str | None = None) -> dict[str, Any]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("email required")
    key = api_key or mv_key()
    if not key:
        raise SystemExit("missing MILLIONVERIFIER_API_KEY")
    out = decide(millionverifier(email, key))
    out["email"] = email
    return out


def credits(api_key: str | None = None) -> Any:
    key = api_key or mv_key()
    _, data = http_json(CREDITS_URL + "?" + urllib.parse.urlencode({"api": key}))
    return data


def main() -> int:
    load_env()
    p = argparse.ArgumentParser(description="verify.md email deliverability decision")
    p.add_argument("email", nargs="?")
    p.add_argument("--demo", choices=sorted(DEMO_KEYS), help="MillionVerifier canned demo key")
    p.add_argument("--credits", action="store_true")
    args = p.parse_args()
    if args.credits:
        print(json.dumps(credits(), indent=2))
        return 0
    if not args.email:
        p.error("email required")
    key = DEMO_KEYS[args.demo] if args.demo else None
    print(json.dumps(verify_email(args.email, key), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

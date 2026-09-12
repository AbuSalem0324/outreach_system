#!/usr/bin/env python3
"""verify.md — one email in, deliverability decision out.

Writes contacts.email_verification_status. No drafting.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ENV_PATHS = (
    Path("/root/.hermes/.env"),
    Path("/root/hermes/.env"),
)

VERIFY_URL = "https://api.millionverifier.com/api/v3/"
TIMEOUT_S = 10

DEMO_KEYS = {
    "ok": "API_KEY_FOR_OK",
    "invalid": "API_KEY_FOR_INVALID",
    "catch_all": "API_KEY_FOR_CATCH_ALL",
    "disposable": "API_KEY_FOR_DISPOSABLE",
    "unknown": "API_KEY_FOR_UNKOWN",  # MillionVerifier's spelling
    "error": "API_KEY_FOR_ERROR_INSUFFICIENT_CREDITS",
}

DECISION = {
    "ok": "proceed",
    "catch_all": "hold",
    "unknown": "hold",
    "invalid": "drop",
    "disposable": "drop",
}

WRITEBACK_RESULTS = frozenset(DECISION)
SSL_CTX = ssl.create_default_context()


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip("'").strip('"')


def mv_key() -> str:
    return os.environ.get("MILLIONVERIFIER_API_KEY") or os.environ.get("MILLIONVERIFIER_KEY") or ""


def _sb_headers() -> dict[str, str]:
    key = os.environ["SUPABASE_SECRET_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _http_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    body = None
    headers = {"User-Agent": "DataBardVerify/0.1", "Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        if method == "GET":
            method = "POST"
    if url.startswith(os.environ.get("SUPABASE_URL", "https://invalid.invalid")):
        headers.update(_sb_headers())
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S + 5, context=SSL_CTX) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            data = {"error": raw.decode("utf-8", errors="replace")[:400]}
        return exc.code, data


def lookup_contact(*, email: str | None = None, contact_id: str | None = None) -> dict[str, Any] | None:
    params: dict[str, str] = {"select": "id,email,status,email_verification_status", "limit": "1"}
    if contact_id:
        params["id"] = f"eq.{contact_id}"
    elif email:
        params["email"] = f"eq.{email.strip().lower()}"
    else:
        return None
    qs = urllib.parse.urlencode(params)
    status, data = _http_json(os.environ["SUPABASE_URL"].rstrip("/") + f"/rest/v1/contacts?{qs}")
    if status >= 300:
        raise RuntimeError(f"contacts lookup HTTP {status}: {data}")
    rows = data or []
    return rows[0] if rows else None


def write_verification_status(contact_id: str, value: str) -> dict[str, Any]:
    headers = _sb_headers()
    headers["Prefer"] = "return=representation"
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/contacts?id=eq." + urllib.parse.quote(contact_id)
    body = json.dumps({"email_verification_status": value}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
        raw = resp.read()
        rows = json.loads(raw.decode("utf-8")) if raw else []
        return rows[0] if rows else {"id": contact_id, "email_verification_status": value}


def millionverifier(email: str, api_key: str) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"api": api_key, "email": email, "timeout": TIMEOUT_S})
    status, data = _http_json(VERIFY_URL + "?" + qs)
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
        "writeback": None,
    }
    if error:
        out["decision"] = "hold"
        out["reason"] = "api_error"
        out["result"] = None
        out["writeback"] = None  # leave not_checked
        return out
    if result not in DECISION:
        out["decision"] = "hold"
        out["reason"] = "unknown"
        out["writeback"] = "unknown"
        return out
    out["decision"] = DECISION[result]
    out["reason"] = result
    out["writeback"] = result
    return out


def verify_email(
    email: str,
    *,
    contact_id: str | None = None,
    api_key: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("email required")
    key = api_key or mv_key()
    if not key:
        raise SystemExit("missing MILLIONVERIFIER_API_KEY")

    contact = None
    if write:
        contact = lookup_contact(contact_id=contact_id, email=None if contact_id else email)

    payload = millionverifier(email, key)
    result = decide(payload)
    result["contact_id"] = (contact or {}).get("id") or contact_id
    result["email"] = email

    if write and result["contact_id"] and result["writeback"] in WRITEBACK_RESULTS:
        written = write_verification_status(result["contact_id"], result["writeback"])
        result["email_verification_status"] = written.get("email_verification_status")
    elif write and result["contact_id"] and result["reason"] == "api_error":
        result["email_verification_status"] = (contact or {}).get("email_verification_status") or "not_checked"
    elif write and not result["contact_id"]:
        result["write_error"] = "no_contact_row"
    else:
        result["email_verification_status"] = result["writeback"]
    return result


def main() -> int:
    for path in ENV_PATHS:
        load_env(path)
    p = argparse.ArgumentParser(description="verify.md email deliverability gate")
    p.add_argument("email")
    p.add_argument("--id", dest="contact_id", help="contacts.id to write back to")
    p.add_argument("--demo", choices=sorted(DEMO_KEYS), help="use MillionVerifier canned demo key")
    p.add_argument("--no-write", action="store_true", help="do not PATCH contacts")
    args = p.parse_args()
    key = DEMO_KEYS[args.demo] if args.demo else None
    out = verify_email(args.email, contact_id=args.contact_id, api_key=key, write=not args.no_write)
    print(json.dumps(out, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

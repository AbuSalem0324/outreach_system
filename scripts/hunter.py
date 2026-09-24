#!/usr/bin/env python3
"""Hunter.io domain-search. Fetch only; no ranking, no send target."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from typing import Any

from common import http_json, load_env, log

HUNTER_SEARCH = "https://api.hunter.io/v2/domain-search"


def _item(e: dict[str, Any], *, kind: str) -> dict[str, Any]:
    first = (e.get("first_name") or "").strip()
    last = (e.get("last_name") or "").strip()
    return {
        "email": (e.get("value") or "").strip().lower(),
        "name": f"{first} {last}".strip(),
        "position": e.get("position"),
        "department": e.get("department"),
        "seniority": e.get("seniority"),
        "confidence": e.get("confidence"),
        "kind": kind,
    }


def hunt_domain(domain: str | None) -> dict[str, Any]:
    """One domain-search. Personals and generics split. Never raises."""
    if not domain:
        return {"status": "no_domain", "personals": [], "generics": [], "pattern": None}
    key = os.environ.get("HUNTER_API_KEY")
    if not key:
        return {"status": "no_key", "personals": [], "generics": [], "pattern": None}
    qs = urllib.parse.urlencode({"domain": domain, "api_key": key})
    status, data = http_json(f"{HUNTER_SEARCH}?{qs}", timeout=15)
    if status == 429:
        log("stage=hunter", domain=domain, note="rate_limited")
        return {"status": "rate_limited", "http": status, "personals": [], "generics": [], "pattern": None}
    if status >= 300 or not isinstance(data, dict):
        log("stage=hunter", domain=domain, http=status)
        return {"status": "error", "http": status, "personals": [], "generics": [], "pattern": None}
    payload = data.get("data") or {}
    personals: list[dict[str, Any]] = []
    generics: list[dict[str, Any]] = []
    seen: set[str] = set()
    for e in payload.get("emails") or []:
        if not isinstance(e, dict):
            continue
        email = (e.get("value") or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        kind = (e.get("type") or "personal").strip().lower()
        if kind == "generic":
            generics.append(_item(e, kind="generic"))
        else:
            personals.append(_item(e, kind="personal"))
    out = {
        "status": "ok",
        "domain": payload.get("domain") or domain,
        "pattern": payload.get("pattern"),
        "organization": payload.get("organization"),
        "personals": personals,
        "generics": generics,
    }
    log("stage=hunter", domain=domain, personals=len(personals), generics=len(generics))
    return out


def main() -> int:
    load_env()
    if len(sys.argv) != 2:
        raise SystemExit("usage: hunter.py <domain>")
    print(json.dumps(hunt_domain(sys.argv[1].strip().lower()), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

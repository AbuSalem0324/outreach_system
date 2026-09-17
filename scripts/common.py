#!/usr/bin/env python3
"""Shared helpers for the outreach scripts. No business logic lives here."""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENV_PATHS = (
    Path("/root/.hermes/.env"),
    Path("/root/hermes/.env"),
)
USER_AGENT = "DataBardOutreach/2.0 (+https://databard.xyz)"
SSL_CTX = ssl.create_default_context()
UNSUB_URL = "https://www.databard.net/unsubscribe?e={email}"
SOURCE = "endole_campaign"
DAILY_CAP = 10


def log(msg: str, **fields: Any) -> None:
    if fields:
        extras = " ".join(f"{k}={_fmt(v)}" for k, v in fields.items())
        print(f"{msg} {extras}", file=sys.stderr, flush=True)
    else:
        print(msg, file=sys.stderr, flush=True)


def _fmt(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def load_env() -> None:
    for path in ENV_PATHS:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip("'").strip('"')


def require_env(*names: str) -> dict[str, str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)}")
    return {n: os.environ[n] for n in names}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalise_company_number(value: str | None) -> str | None:
    if not value:
        return None
    v = re.sub(r"\s", "", str(value)).upper()
    if not v:
        return None
    if v.isdigit():
        return v.zfill(8)
    return v


def domain_from_website(website: str | None) -> str | None:
    if not website:
        return None
    w = website.strip()
    parsed = urllib.parse.urlparse(w if "://" in w else f"https://{w}")
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    host = host.split(":")[0].strip("/")
    return host or None


def domain_from_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[-1].strip().lower() or None


def slug(value: str | None, fallback: str = "company") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s[:60] or fallback


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: Any = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, Any]:
    body = None
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw.decode("utf-8")) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            data = {"error": raw.decode("utf-8", errors="replace")[:400]}
        return exc.code, data


class Supabase:
    """Thin PostgREST client using the secret key. RLS is bypassed by design."""

    def __init__(self) -> None:
        env = require_env("SUPABASE_URL", "SUPABASE_SECRET_KEY")
        self.base = env["SUPABASE_URL"].rstrip("/") + "/rest/v1/"
        key = env["SUPABASE_SECRET_KEY"]
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    def _call(self, method: str, path: str, *, params: dict[str, str] | None = None,
              payload: Any = None, prefer: str | None = None) -> Any:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        status, data = http_json(url, method=method, payload=payload, headers=headers)
        if status >= 300:
            raise RuntimeError(f"supabase {method} {path} HTTP {status}: {data}")
        return data

    def select(self, table: str, **params: str) -> list[dict[str, Any]]:
        return self._call("GET", table, params=params) or []

    def insert(self, table: str, rows: Any, *, upsert_on: str | None = None) -> list[dict[str, Any]]:
        params = {"on_conflict": upsert_on} if upsert_on else None
        prefer = "return=representation" + (",resolution=merge-duplicates" if upsert_on else "")
        data = self._call("POST", table, params=params, payload=rows, prefer=prefer)
        return data if isinstance(data, list) else [data]

    def patch(self, table: str, filters: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = self._call("PATCH", table, params=filters, payload=payload, prefer="return=representation")
        return data if isinstance(data, list) else [data]

    def rpc(self, fn: str, payload: dict[str, Any] | None = None) -> Any:
        return self._call("POST", f"rpc/{fn}", payload=payload or {})

    # Convenience

    def first_touches_today(self) -> int:
        return int(self.rpc("first_touches_today") or 0)

    def quota_remaining(self) -> int:
        return max(0, DAILY_CAP - self.first_touches_today())

    def contact_by_email(self, email: str) -> dict[str, Any] | None:
        rows = self.select("contacts", email=f"eq.{email.strip().lower()}", limit="1")
        return rows[0] if rows else None

    def set_outcome(self, company_number: str, outcome: str, reason: str | None = None) -> None:
        payload: dict[str, Any] = {"outcome": outcome, "last_checked_at": now_iso()}
        if reason is not None:
            payload["reason"] = reason[:500]
        self.patch("companies_seen", {"company_number": f"eq.{company_number}"}, payload)


class Telegram:
    def __init__(self) -> None:
        env = require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        self.api = f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}"
        self.chat_id = env["TELEGRAM_CHAT_ID"]

    def send_document(self, filename: str, content: str, caption: str | None = None) -> int:
        """Multipart upload of an in-memory text file. Returns message_id."""
        boundary = "----DataBardBoundary7MA4YWxkTrZu0gW"
        parts: list[bytes] = []

        def field(name: str, value: str) -> None:
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
            )

        field("chat_id", self.chat_id)
        if caption:
            field("caption", caption[:1000])
        parts.append(
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            ).encode()
            + content.encode("utf-8")
            + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        req = urllib.request.Request(
            f"{self.api}/sendDocument",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": USER_AGENT},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            raise RuntimeError(f"telegram sendDocument failed: {data}")
        return int(data["result"]["message_id"])

    def send_text(self, text: str) -> int:
        status, data = http_json(
            f"{self.api}/sendMessage",
            method="POST",
            payload={"chat_id": self.chat_id, "text": text[:4000], "disable_web_page_preview": True},
        )
        if status >= 300 or not (data or {}).get("ok"):
            raise RuntimeError(f"telegram sendMessage failed: {data}")
        return int(data["result"]["message_id"])


def draft_file(to: str, subject: str, body: str) -> str:
    return f"To: {to}\nSubject: {subject}\n\n{body.rstrip()}\n"


def first_name(full: str | None) -> str | None:
    if not full:
        return None
    parts = [p for p in re.split(r"\s+", full.strip()) if p]
    if not parts:
        return None
    # Skip honorifics
    while parts and parts[0].rstrip(".").lower() in {"mr", "mrs", "ms", "miss", "dr", "sir"}:
        parts = parts[1:]
    return parts[0] if parts else None


# ---------------------------------------------------------------------------
# Companies House: resolve a registered name (+ postcode) to a company number
# ---------------------------------------------------------------------------

CH_BASE = "https://api.company-information.service.gov.uk"


def ch_auth_headers() -> dict[str, str] | None:
    import base64

    key = next((os.environ[n] for n in ("COMPANY_HOUSE", "COMPANIES_HOUSE_API_KEY", "CH_API_KEY") if os.environ.get(n)), None)
    if not key:
        return None
    return {"Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()}


def _pc(value: str | None) -> str:
    return re.sub(r"\s", "", (value or "")).upper()


def _name_key(value: str | None) -> str:
    v = re.sub(r"[^a-z0-9 ]", " ", (value or "").lower())
    v = re.sub(r"\b(limited|ltd|plc|llp|the|and|&)\b", " ", v)
    return re.sub(r"\s+", " ", v).strip()


def ch_resolve_company_number(name: str, postcode: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
    """Search CH by name; accept a hit if the postcode matches or the name is an exact key match.

    Returns (company_number, hit) or (None, None). Deterministic, no judgement.
    """
    hdrs = ch_auth_headers()
    if not hdrs or not name:
        return None, None
    qs = urllib.parse.urlencode({"q": name, "items_per_page": 10})
    status, data = http_json(f"{CH_BASE}/search/companies?{qs}", headers=hdrs)
    if status >= 300 or not isinstance(data, dict):
        return None, None
    items = data.get("items") or []
    want_pc = _pc(postcode)
    want_name = _name_key(name)
    best = None
    for it in items:
        addr = it.get("address") or {}
        pc_match = bool(want_pc) and _pc(addr.get("postal_code")) == want_pc
        name_match = _name_key(it.get("title")) == want_name
        active = (it.get("company_status") or "").lower() == "active"
        score = (pc_match and name_match, pc_match and active, pc_match, name_match and active, name_match)
        if any(score) and (best is None or score > best[0]):
            best = (score, it)
    if not best:
        return None, None
    hit = best[1]
    return normalise_company_number(hit.get("company_number")), {
        "title": hit.get("title"),
        "company_number": hit.get("company_number"),
        "company_status": hit.get("company_status"),
        "postal_code": (hit.get("address") or {}).get("postal_code"),
        "matched_on": "postcode" if _pc((hit.get("address") or {}).get("postal_code")) == want_pc else "name",
    }

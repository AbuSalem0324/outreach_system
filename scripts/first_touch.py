#!/usr/bin/env python3
"""First-touch copy. Fixed pieces are constants here; Hermes supplies one
sentence. draft.md describes the same structure for humans, and
tests/test_first_touch.py fails if the two drift apart.
"""

from __future__ import annotations

from common import UNSUB_URL, first_name
from followups import WHO as WHO_WRAPPED

DEFAULT_ICP = "home-turf-fmcg-v1"

SUBJECT = "Forecasting and reporting for food manufacturers"
WHO = " ".join(WHO_WRAPPED.split())
OFFER = (
    "A small forecasting or reporting tool, built around the current workflow, "
    "can sit next to how the operation already runs, without the learning curve "
    "or the cost of an enterprise system most of which would go unused."
)
ASK = "Happy to do a short call if that's useful."
SIGN_OFF = "Adam"
CLOSING = "Not relevant? Let me know."

# Only ICPs with written copy. ICP B has a subject in draft.md but no
# "who" paragraph yet, so it is refused until someone writes one.
COPY_BY_ICP = {DEFAULT_ICP: {"subject": SUBJECT, "who": WHO}}

GENERIC_LOCALS = {
    "info", "sales", "enquiries", "enquiry", "hello", "office", "admin", "reception",
    "contact", "accounts", "orders", "mail", "team", "support", "customerservice",
    "customerservices", "general", "help",
}
SOURCE_CITING = (
    "your filing", "companies house", "i saw", "i noticed", "i see that", "on your site",
    "on your website", "your team page", "according to", "endole", "hunter",
)
MAX_SENTENCE_CHARS = 400


def check_sentence(label: str, text: str) -> str:
    """Mechanical checks only. Raises SystemExit naming the fix."""
    s = (text or "").strip()
    if not s:
        raise SystemExit(f"{label} is empty; write one sentence")
    if "\n" in s:
        raise SystemExit(f"{label} has a line break; write one sentence on one line")
    if "—" in s:
        raise SystemExit(f"{label} has an em dash; rewrite without it")
    if len(s) > MAX_SENTENCE_CHARS:
        raise SystemExit(f"{label} is {len(s)} characters; one sentence, under {MAX_SENTENCE_CHARS}")
    if s[-1] not in ".?!":
        raise SystemExit(f"{label} must be a complete sentence ending in a full stop")
    low = s.lower()
    hit = next((p for p in SOURCE_CITING if p in low), None)
    if hit:
        raise SystemExit(f'{label} cites its source ("{hit}"); say what matters, not where it came from')
    return s


def is_generic_inbox(email: str) -> bool:
    return email.split("@", 1)[0].lower() in GENERIC_LOCALS


def greeting(email: str, buyer_name: str | None) -> str:
    name = None if is_generic_inbox(email) else first_name(buyer_name)
    return f"Hi {name}," if name else "Hi,"


def build(icp_id: str | None, email: str, buyer_name: str | None, relevance: str) -> tuple[str, str]:
    """Return (subject, body) for the first touch."""
    icp = icp_id or DEFAULT_ICP
    copy = COPY_BY_ICP.get(icp)
    if not copy:
        raise SystemExit(f"no first-touch copy for icp {icp}; add it to scripts/first_touch.py")
    sentence = check_sentence("--relevance", relevance)
    body = "\n\n".join(
        [
            greeting(email, buyer_name),
            copy["who"],
            f"{sentence} {OFFER}",
            ASK,
            SIGN_OFF,
            f"{CLOSING}\n{UNSUB_URL.format(email=email)}",
        ]
    )
    return copy["subject"], body + "\n"

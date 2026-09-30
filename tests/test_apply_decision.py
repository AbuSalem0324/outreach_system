import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from send_and_log_listener import apply_decision  # noqa: E402


class FakeDb:
    def __init__(self, messages=None, contacts=None):
        self.messages = messages or []
        self.contacts = contacts or []
        self.rpc_calls = []
        self.patches = []

    def select(self, table, **params):
        if table == "messages":
            mid = params.get("telegram_message_id", "").removeprefix("eq.")
            outcome = params.get("outcome", "").removeprefix("eq.")
            return [m for m in self.messages if str(m.get("telegram_message_id")) == mid and m.get("outcome") == outcome]
        if table == "contacts":
            mid = params.get("telegram_message_id", "").removeprefix("eq.")
            return [c for c in self.contacts if str(c.get("telegram_message_id")) == mid]
        raise AssertionError(table)

    def rpc(self, fn, payload):
        self.rpc_calls.append((fn, payload))
        return {"id": "m1"}

    def patch(self, table, filters, payload):
        self.patches.append((table, filters, payload))
        return [payload]


class ApplyDecision(unittest.TestCase):
    def test_pending_thumb_resolves_done(self):
        db = FakeDb(messages=[{"telegram_message_id": 9, "outcome": "pending"}])
        apply_decision(db, 9, ["👍"])
        self.assertEqual(db.rpc_calls, [("resolve_touch", {"p_telegram_message_id": 9, "p_outcome": "done"})])
        self.assertEqual(db.patches, [])

    def test_pending_down_resolves_skipped(self):
        db = FakeDb(messages=[{"telegram_message_id": 9, "outcome": "pending"}])
        apply_decision(db, 9, ["👎"])
        self.assertEqual(db.rpc_calls[0][1]["p_outcome"], "skipped")

    def test_pending_handshake_resolves_responded(self):
        db = FakeDb(messages=[{"telegram_message_id": 9, "outcome": "pending"}])
        apply_decision(db, 9, ["🤝"])
        self.assertEqual(db.rpc_calls[0][1]["p_outcome"], "responded")

    def test_handshake_wins_over_thumb(self):
        db = FakeDb(messages=[{"telegram_message_id": 9, "outcome": "pending"}])
        apply_decision(db, 9, ["👍", "🤝"])
        self.assertEqual(db.rpc_calls[0][1]["p_outcome"], "responded")

    def test_pending_unknown_emoji_does_not_resolve(self):
        db = FakeDb(messages=[{"telegram_message_id": 9, "outcome": "pending"}])
        apply_decision(db, 9, ["🔥"])
        self.assertEqual(db.rpc_calls, [])

    def test_draft_thumb_still_logs_contact(self):
        db = FakeDb(contacts=[{
            "id": "c1", "email": "a@b.c", "company_name": "Co", "domain": "b.c",
            "status": "new", "notes": None, "draft_subject": "S", "draft_body": "B",
            "telegram_message_id": 4,
        }])
        apply_decision(db, 4, ["👍"])
        self.assertEqual(db.rpc_calls[0][0], "log_contact")
        self.assertFalse(any(call[0] == "resolve_touch" for call in db.rpc_calls))

    def test_first_touch_down_still_skips(self):
        db = FakeDb(contacts=[{
            "id": "c1", "email": "a@b.c", "status": "new", "telegram_message_id": 4,
            "company_name": "Co", "domain": "b.c", "notes": None, "draft_subject": "S", "draft_body": "B",
        }])
        apply_decision(db, 4, ["👎"])
        self.assertEqual(db.patches[0][2]["status"], "skipped")
        self.assertEqual(db.rpc_calls, [])

    def test_followup_down_still_closes(self):
        db = FakeDb(contacts=[{
            "id": "c1", "email": "a@b.c", "status": "contacted", "telegram_message_id": 4,
            "company_name": "Co", "domain": "b.c", "notes": None, "draft_subject": "S", "draft_body": "B",
        }])
        apply_decision(db, 4, ["👎"])
        self.assertEqual(db.patches[0][2]["status"], "closed")

    def test_unknown_message_is_ignored(self):
        db = FakeDb()
        apply_decision(db, 99, ["👍"])
        self.assertEqual(db.rpc_calls, [])
        self.assertEqual(db.patches, [])

    def test_linkedin_reaction_does_not_log_a_draft(self):
        db = FakeDb(contacts=[{
            "id": "c1", "email": "a@b.c", "status": "new", "telegram_message_id": 4,
            "company_name": "Co", "domain": "b.c", "notes": None, "draft_subject": "S", "draft_body": "B",
        }])
        apply_decision(db, 4, ["👍"], scope="linkedin")
        self.assertEqual(db.rpc_calls, [])
        self.assertEqual(db.patches, [])

    def test_linkedin_reaction_resolves_linkedin_task(self):
        db = FakeDb(messages=[{"telegram_message_id": 4, "outcome": "pending", "channel": "linkedin"}])
        apply_decision(db, 4, ["👍"], scope="linkedin")
        self.assertEqual(db.rpc_calls[0][1]["p_outcome"], "done")

    def test_main_reaction_ignores_linkedin_task(self):
        db = FakeDb(messages=[{"telegram_message_id": 4, "outcome": "pending", "channel": "linkedin"}])
        apply_decision(db, 4, ["👍"], scope="main")
        self.assertEqual(db.rpc_calls, [])

    def test_collision_is_not_resolved(self):
        db = FakeDb(messages=[
            {"telegram_message_id": 4, "outcome": "pending", "channel": "linkedin"},
            {"telegram_message_id": 4, "outcome": "pending", "channel": "letter"},
        ])
        apply_decision(db, 4, ["👍"], scope="linkedin")
        apply_decision(db, 4, ["👍"], scope="main")
        self.assertEqual(db.rpc_calls, [])


if __name__ == "__main__":
    unittest.main()

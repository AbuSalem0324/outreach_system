import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import deliver  # noqa: E402
import pick  # noqa: E402

ANGLE = "You're running production and your own fleet from one site, which is where planning gets complicated."
REL = "This could be useful for Example Foods because production, your own fleet and scheduling all run from one site."


class Tg:
    sent = []

    def send_text(self, text):
        Tg.sent.append(("text", text))
        return 11

    def send_document(self, filename, content, caption):
        Tg.sent.append(("doc", filename, caption, content))
        return 12


class Db:
    def __init__(self):
        self.row = {"company_number": "01234567", "company_name": "Example Foods Ltd", "domain": "example.com",
                    "website": "https://example.com", "icp_id": "home-turf-fmcg-v1", "campaign_id": "c1",
                    "outcome": "in_research", "raw": {}}
        self.contacts = []

    def select(self, table, **p):
        return [self.row] if table == "companies_seen" else []

    def insert(self, table, row):
        self.contacts.append(row)
        return [{"id": "k1"}]

    def patch(self, *a, **k):
        return []

    def set_outcome(self, cn, outcome, reason=None):
        self.row.update(outcome=outcome, reason=reason)


def payload(**over):
    base = {"company_number": "01234567", "company_name": "Example Foods Ltd", "angle": ANGLE, "relevance": REL,
            "postal_address": "1 Mill Lane, Bolton BL1 1AA",
            "candidates": [
                {"email": "jane@example.com", "name": "Jane Roe", "position": "Operations Director", "kind": "personal", "reason": "ops"},
                {"email": "tom@example.com", "name": "Tom Poe", "position": "Finance Director", "kind": "personal",
                 "reason": "finance", "phone": "+44 161 000 0000", "phone_type": "direct"},
                {"email": "info@example.com", "name": "Front Desk", "position": "", "kind": "generic", "reason": "shared inbox"}]}
    return {**base, **over}


class PickerFlow(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        pick.PICKS_DIR = self.dir
        pick.load_env = lambda: None
        pick.Telegram = deliver.Telegram = Tg
        Tg.sent = []
        self.db = Db()
        pick.Supabase = lambda: self.db
        deliver.check_email = lambda *a, **k: {"decision": "clear", "reason": "no_history"}
        deliver.verify_email = lambda email: {"decision": "proceed", "reason": "ok", "result": "ok"}

    def offer(self, **over):
        f = self.dir / "in.json"
        f.write_text(json.dumps(payload(**over)))
        return pick.cmd_offer(argparse.Namespace(company_number="01234567", file=str(f)))

    def send(self, choice, relevance=""):
        return pick.cmd_send(argparse.Namespace(company_number="01234567", choice=choice, relevance=relevance), db=self.db)

    def test_offer_posts_the_options_and_waits(self):
        self.offer()
        self.assertEqual(self.db.row["outcome"], "awaiting_pick")
        text = Tg.sent[0][1]
        self.assertIn("2. tom@example.com: Tom Poe, Finance Director", text)
        self.assertIn("o/to 01234567 N", text)
        self.assertNotIn("—", text)
        self.assertEqual(self.db.contacts, [])

    def test_pick_by_number_delivers_the_draft_to_that_person(self):
        self.offer()
        self.assertEqual(self.send("2"), 0)
        contact = self.db.contacts[0]
        self.assertEqual((contact["email"], contact["buyer_name"], contact["angle"]), ("tom@example.com", "Tom Poe", ANGLE))
        self.assertEqual((contact["phone"], contact["phone_type"], contact["postal_address"]),
                         ("+44 161 000 0000", "direct", "1 Mill Lane, Bolton BL1 1AA"))
        doc = Tg.sent[-1]
        self.assertTrue(doc[3].startswith("To: tom@example.com\n"))
        self.assertIn("Hi Tom,", doc[3])
        self.assertIn(REL, doc[3])
        self.assertEqual(self.db.row["outcome"], "promoted_to_contacts")

    def test_pick_by_email_and_generic_gets_no_first_name(self):
        self.offer()
        self.send("info@example.com")
        self.assertIsNone(self.db.contacts[0]["buyer_name"])
        self.assertIn("\n\nHi,\n\n", Tg.sent[-1][3])

    def test_offer_refuses_a_missing_or_bad_sentence(self):
        for over in ({"relevance": ""}, {"angle": "I noticed you run a fleet."}):
            with self.subTest(over=over), self.assertRaises(SystemExit):
                self.offer(**over)
        self.assertEqual(self.db.row["outcome"], "in_research")

    def test_offer_needs_two_candidates(self):
        with self.assertRaises(SystemExit):
            self.offer(candidates=payload()["candidates"][:1])

    def test_failed_verification_keeps_the_picker_open(self):
        self.offer()
        deliver.verify_email = lambda email: {"decision": "drop", "reason": "invalid", "result": "invalid"}
        self.assertEqual(self.send("1"), 5)
        self.assertEqual(self.db.row["outcome"], "awaiting_pick")
        self.assertEqual(self.db.contacts, [])
        deliver.verify_email = lambda email: {"decision": "proceed", "reason": "ok", "result": "ok"}
        self.assertEqual(self.send("2"), 0)

    def test_old_picker_without_relevance_needs_one_passed(self):
        (self.dir / "01234567.json").write_text(json.dumps({k: v for k, v in payload().items() if k != "relevance"}))
        self.db.row["outcome"] = "awaiting_pick"
        with self.assertRaises(SystemExit) as cm:
            self.send("1")
        self.assertIn("--relevance", str(cm.exception))
        self.assertEqual(self.send("1", relevance=REL), 0)

    def test_choice_out_of_range(self):
        self.offer()
        with self.assertRaises(SystemExit):
            self.send("9")


if __name__ == "__main__":
    unittest.main()

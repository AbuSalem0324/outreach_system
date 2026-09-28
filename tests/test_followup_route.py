import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from followups import build, call_text, letter_text, linkedin_text, route  # noqa: E402


def contact(**extra):
    base = {
        "id": "c1",
        "email": "jane@example.com",
        "company_name": "Example Ltd",
        "buyer_name": "Jane Roe",
        "angle": "Production and a fleet from one site.",
        "contact_count": 1,
        "icp_id": "home-turf-fmcg-v1",
    }
    base.update(extra)
    return base


class Route(unittest.TestCase):
    def test_touch_2_is_email_only(self):
        self.assertEqual(route(contact(contact_count=1), []), [{"kind": "email", "step": 2}])

    def test_touch_3_without_linkedin_is_email_only(self):
        self.assertEqual(route(contact(contact_count=2), []), [{"kind": "email", "step": 3}])

    def test_touch_3_with_linkedin_adds_task(self):
        got = route(contact(contact_count=2, linkedin_url="https://www.linkedin.com/in/example"), [])
        self.assertEqual(got, [{"kind": "email", "step": 3}, {"kind": "linkedin", "step": 3}])

    def test_existing_linkedin_row_is_not_reposted(self):
        messages = [{"channel": "linkedin", "sequence_step": 3, "outcome": "done"}]
        got = route(contact(contact_count=2, linkedin_url="https://www.linkedin.com/in/example"), messages)
        self.assertEqual(got, [{"kind": "email", "step": 3}])

    def test_letter_when_postal_set(self):
        got = route(contact(contact_count=3, postal_address="1 Mill Lane"), [])
        self.assertEqual(got, [{"kind": "letter", "step": 4}])

    def test_call_when_no_postal(self):
        got = route(contact(contact_count=3, phone="+44161"), [])
        self.assertEqual(got, [{"kind": "call", "step": 4}])

    def test_close_when_nothing_left(self):
        self.assertEqual(route(contact(contact_count=3), []), [{"kind": "close", "step": 4}])

    def test_pending_blocks_everything(self):
        messages = [{"channel": "letter", "sequence_step": 4, "outcome": "pending"}]
        got = route(contact(contact_count=3, postal_address="1 Mill Lane", phone="+44161"), messages)
        self.assertEqual(got, [])

    def test_resolved_letter_unlocks_call(self):
        for outcome in ("done", "skipped"):
            messages = [{"channel": "letter", "sequence_step": 4, "outcome": outcome}]
            got = route(contact(contact_count=3, phone="+44161", postal_address="1 Mill Lane"), messages)
            self.assertEqual(got, [{"kind": "call", "step": 4}])

    def test_resolved_letter_without_phone_closes(self):
        messages = [{"channel": "letter", "sequence_step": 4, "outcome": "done"}]
        self.assertEqual(route(contact(contact_count=3, postal_address="1 Mill Lane"), messages), [{"kind": "close", "step": 4}])

    def test_existing_phone_row_is_not_reposted(self):
        messages = [
            {"channel": "letter", "sequence_step": 4, "outcome": "done"},
            {"channel": "phone", "sequence_step": 4, "outcome": "skipped"},
        ]
        got = route(contact(contact_count=3, phone="+44161"), messages)
        self.assertEqual(got, [])

    def test_responded_letter_does_not_call(self):
        messages = [{"channel": "letter", "sequence_step": 4, "outcome": "responded"}]
        got = route(contact(contact_count=3, phone="+44161"), messages)
        self.assertEqual(got, [])


class TaskText(unittest.TestCase):
    def test_letter_has_opt_out_and_no_em_dash(self):
        text = letter_text(contact(postal_address="1 Mill Lane, Bolton BL1 1AA", buyer_role="Operations Director"))
        self.assertIn("1 Mill Lane, Bolton BL1 1AA", text)
        self.assertIn("https://www.databard.net/unsubscribe?e=jane@example.com", text)
        self.assertIn("If you'd rather I didn't write again", text)
        self.assertNotIn("\u2014", text)
        self.assertNotIn("handwritten", text)

    def test_call_mobile_mentions_tps(self):
        text = call_text(contact(phone="+447700900000", phone_type="mobile", buyer_role="Owner"))
        self.assertIn("Corporate TPS", text)
        self.assertIn("Check TPS as well", text)
        self.assertNotIn("\u2014", text)

    def test_call_switchboard_skips_personal_tps(self):
        text = call_text(contact(phone="+44161", phone_type="switchboard"))
        self.assertIn("Corporate TPS", text)
        self.assertNotIn("Check TPS as well", text)

    def test_linkedin_forbids_a_pitch(self):
        text = linkedin_text(contact(linkedin_url="https://www.linkedin.com/in/example", buyer_role="MD"))
        self.assertIn("No pitch in the note", text)
        self.assertIn("https://www.linkedin.com/in/example", text)
        self.assertNotIn("\u2014", text)
    def test_touch_3_is_not_the_last_one(self):
        _subject, body = build(contact(contact_count=2), 3)
        self.assertNotIn("Last one from me", body)
        self.assertIn("One more note on this", body)
        self.assertIn("https://www.databard.net/unsubscribe?e=jane@example.com", body)

    def test_touch_2_unchanged_opener(self):
        _subject, body = build(contact(), 2)
        self.assertIn("Following up on my note", body)


if __name__ == "__main__":
    unittest.main()

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import first_touch as ft  # noqa: E402
from common import research_card  # noqa: E402

GOOD = "This could be useful for Example Ltd because production and your own fleet run from one site."


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class Build(unittest.TestCase):
    def test_personal_address_gets_first_name_and_all_fixed_pieces(self):
        subject, body = ft.build("home-turf-fmcg-v1", "jane@example.com", "Mrs Jane Roe", GOOD)
        self.assertEqual(subject, ft.SUBJECT)
        self.assertEqual(
            body.split("\n\n"),
            [
                "Hi Jane,",
                ft.WHO,
                f"{GOOD} {ft.OFFER}",
                ft.ASK,
                "Adam",
                "Not relevant? Let me know.\nhttps://www.databard.net/unsubscribe?e=jane@example.com\n",
            ],
        )

    def test_generic_inbox_never_gets_a_first_name(self):
        _, body = ft.build(None, "info@example.com", "Jane Roe", GOOD)
        self.assertTrue(body.startswith("Hi,\n\n"))

    def test_no_name_is_role_addressed(self):
        _, body = ft.build(None, "jane@example.com", "", GOOD)
        self.assertTrue(body.startswith("Hi,\n\n"))

    def test_icp_without_copy_is_refused(self):
        with self.assertRaises(SystemExit):
            ft.build("generalist-control-v1", "jane@example.com", "Jane Roe", GOOD)

    def test_fixed_copy_has_no_em_dash(self):
        _, body = ft.build(None, "jane@example.com", "Jane Roe", GOOD)
        self.assertNotIn("—", body)


class CheckSentence(unittest.TestCase):
    def test_good_sentence_passes_trimmed(self):
        self.assertEqual(ft.check_sentence("--angle", f"  {GOOD} "), GOOD)

    def test_refusals(self):
        bad = [
            "",
            "No full stop",
            "An em dash — here.",
            "Two\nlines.",
            "Your filing shows a move to small company status.",
            "I noticed you run your own fleet.",
            "x" * 400 + ".",
        ]
        for text in bad:
            with self.subTest(text=text[:30]), self.assertRaises(SystemExit):
                ft.check_sentence("--relevance", text)


class DocsAgreeWithCode(unittest.TestCase):
    def test_draft_md_holds_the_same_constants(self):
        draft = flat((ROOT / "draft.md").read_text(encoding="utf-8"))
        for piece in (ft.SUBJECT, ft.WHO, ft.OFFER, ft.ASK, ft.CLOSING):
            self.assertIn(piece, draft)

    def test_card_lists_every_active_buyer_title(self):
        icp = (ROOT / "icp-definitions.md").read_text(encoding="utf-8")
        block = icp.split("icp_id: home-turf-fmcg-v1", 1)[1].split("```", 1)[0]
        titles = re.findall(r"^  - (.+)$", block.split("buyer_titles:", 1)[1].split("pitch_angle:", 1)[0], re.M)
        self.assertEqual(len(titles), 5)
        card = flat(research_card())
        for title in titles:
            self.assertIn(title, card)

    def test_card_has_no_em_dash(self):
        self.assertNotIn("—", research_card())


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from hunter import _item  # noqa: E402


class ItemFields(unittest.TestCase):
    def test_keeps_linkedin_and_phone(self):
        row = {
            "value": "jane@example.com",
            "first_name": "Jane",
            "last_name": "Roe",
            "position": "Operations Director",
            "department": "operations",
            "seniority": "executive",
            "confidence": 90,
            "type": "personal",
            "linkedin": "https://www.linkedin.com/in/example",
            "phone_number": "+44 161 000 0000",
        }
        got = _item(row, kind="personal")
        self.assertEqual(got["linkedin_url"], "https://www.linkedin.com/in/example")
        self.assertEqual(got["phone"], "+44 161 000 0000")
        self.assertEqual(got["email"], "jane@example.com")

    def test_missing_fields_are_none(self):
        got = _item({"value": "a@b.c", "type": "personal"}, kind="personal")
        self.assertIsNone(got["linkedin_url"])
        self.assertIsNone(got["phone"])

    def test_blank_fields_are_none(self):
        got = _item({"value": "a@b.c", "linkedin": "  ", "phone_number": ""}, kind="personal")
        self.assertIsNone(got["linkedin_url"])
        self.assertIsNone(got["phone"])


if __name__ == "__main__":
    unittest.main()

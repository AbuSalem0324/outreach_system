import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from deliver import enrichment_fields  # noqa: E402


class EnrichmentFields(unittest.TestCase):
    def test_postal_alone_does_not_mark_hunter(self):
        got = enrichment_fields("", "", "", "1 Mill Lane, Bolton BL1 1AA", "2026-09-28T00:00:00Z")
        self.assertEqual(got["postal_address"], "1 Mill Lane, Bolton BL1 1AA")
        self.assertIsNone(got["enrichment_source"])
        self.assertIsNone(got["enriched_at"])

    def test_linkedin_marks_hunter(self):
        got = enrichment_fields(" https://www.linkedin.com/in/example ", "", "", "", "now")
        self.assertEqual(got["linkedin_url"], "https://www.linkedin.com/in/example")
        self.assertEqual(got["enrichment_source"], "hunter")
        self.assertEqual(got["enriched_at"], "now")

    def test_mobile_phone_is_stored(self):
        got = enrichment_fields("", "+447700900000", "mobile", "", "now")
        self.assertEqual(got["phone"], "+447700900000")
        self.assertEqual(got["phone_type"], "mobile")
        self.assertEqual(got["enrichment_source"], "hunter")

    def test_phone_without_type_exits(self):
        with self.assertRaises(SystemExit):
            enrichment_fields("", "+44161", "", "", "now")

    def test_unknown_type_exits(self):
        with self.assertRaises(SystemExit):
            enrichment_fields("", "+44161", "fax", "", "now")

    def test_type_without_phone_exits(self):
        with self.assertRaises(SystemExit):
            enrichment_fields("", "", "direct", "", "now")


if __name__ == "__main__":
    unittest.main()

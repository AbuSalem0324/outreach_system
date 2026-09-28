import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pick import chosen_payload  # noqa: E402


class ChosenPayload(unittest.TestCase):
    def test_person_channels_survive(self):
        payload = {
            "company_number": "01234567",
            "company_name": "Example Ltd",
            "angle": "One sentence.",
            "postal_address": "1 Mill Lane, Bolton BL1 1AA",
        }
        chosen = {
            "email": "jane@example.com",
            "name": "Jane Roe",
            "position": "Operations Director",
            "linkedin_url": "https://www.linkedin.com/in/example",
            "phone": "+44 161 000 0000",
            "phone_type": "direct",
        }
        got = chosen_payload(payload, chosen)
        self.assertEqual(got["postal_address"], "1 Mill Lane, Bolton BL1 1AA")
        self.assertEqual(got["chosen"]["linkedin_url"], "https://www.linkedin.com/in/example")
        self.assertEqual(got["chosen"]["phone"], "+44 161 000 0000")
        self.assertEqual(got["chosen"]["phone_type"], "direct")
        self.assertEqual(got["buyer_name"], "Jane Roe")

    def test_generic_yields_nulls(self):
        got = chosen_payload(
            {"company_number": "01234567", "company_name": "Example Ltd", "angle": "One."},
            {"email": "info@example.com", "name": "", "position": "", "kind": "generic"},
        )
        self.assertIsNone(got["postal_address"])
        self.assertIsNone(got["chosen"]["linkedin_url"])
        self.assertIsNone(got["chosen"]["phone"])
        self.assertIsNone(got["chosen"]["phone_type"])
        self.assertEqual(got["buyer_name"], "")


if __name__ == "__main__":
    unittest.main()

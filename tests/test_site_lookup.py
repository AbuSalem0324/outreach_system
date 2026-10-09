import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("OUTREACH_STATE_DIR", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import next as nx  # noqa: E402
import site_lookup as sl  # noqa: E402

ROW = {
    "company_number": "00321426",
    "company_name": "George Romney Limited",
    "email": "sales@mintcake.example",
    "website": None,
    "domain": "mintcake.example",
    "campaign_id": "c1",
    "outcome": "in_research",
    "raw": {"Postcode": "LA9 6NA", "_mapped": {"postcode": ["Postcode"]}},
}


def site(text, status="ok"):
    return lambda url, verify=False: {"status": status, "final_url": url, "_text": text}


class Freemail(unittest.TestCase):
    def test_providers_and_isps(self):
        for d in ("gmail.com", "hotmail.co.uk", "yahoo.co.uk", "btconnect.com", "live.co.uk", "fenn57.fsnet.co.uk", "zen.co.uk"):
            self.assertTrue(sl.is_freemail(d), d)

    def test_company_domains(self):
        for d in ("seddonfoods.co.uk", "buckleyfoods.com", "livefoods.co.uk", None):
            self.assertFalse(sl.is_freemail(d), d)

    def test_company_domain_never_returns_a_provider(self):
        self.assertIsNone(sl.company_domain({"email": "agafood@gmail.com", "domain": "gmail.com"}))
        self.assertEqual(sl.company_domain({"email": "a@seddonfoods.co.uk", "domain": "seddonfoods.co.uk"}), "seddonfoods.co.uk")


class Grade(unittest.TestCase):
    def g(self, text):
        return sl.grade_text(text, "00321426", "George Romney Limited", "LA9 6NA")

    def test_company_number_with_or_without_leading_zeros(self):
        self.assertEqual(self.g("Registered in England No. 321426")[0], "verified")
        self.assertEqual(self.g("Company number 00321426.")[1], ["company_number"])

    def test_postcode_any_spacing(self):
        self.assertEqual(self.g("Mintsfeet Road, Kendal LA96NA")[0], "verified")

    def test_name_alone_is_only_plausible(self):
        self.assertEqual(self.g("George Romney Ltd, makers of Kendal Mint Cake"), ("plausible", ["registered_name"]))

    def test_namesake_is_unverified(self):
        self.assertEqual(self.g("Romney Marsh Wools, Kent TN29 9SX. Company 07654321")[0], "unverified")

    def test_postcode_from_address_when_no_column(self):
        row = {"raw": {"_address": "Unit 4b Cranfield Road, Lostock, Bolton, Lancs, BL6 4SB"}}
        self.assertEqual(sl.row_postcode(row), "BL6 4SB")


class Resolve(unittest.TestCase):
    def test_email_domain_accepted_on_a_match(self):
        found, tried = sl.resolve(ROW, site("Kendal LA9 6NA"), None)
        self.assertEqual((found["source"], found["grade"], found["domain"]), ("endole_email_domain", "verified", "mintcake.example"))
        self.assertEqual(len(tried), 1)

    def test_email_domain_with_no_match_is_left_for_search(self):
        found, tried = sl.resolve(ROW, site("An accountancy practice in Leeds"), None)
        self.assertIsNone(found)
        self.assertEqual(tried[0]["grade"], "unverified")

    def test_freemail_is_never_fetched(self):
        calls = []
        row = {**ROW, "email": "georgeromney@hotmail.co.uk"}
        found, tried = sl.resolve(row, lambda url, verify=False: calls.append(url) or {"status": "ok"}, None)
        self.assertIsNone(found)
        self.assertEqual(calls, [])
        self.assertIn("freemail", tried[0]["skipped"])

    def test_hunter_guess_needs_more_than_the_name(self):
        row = {**ROW, "email": None}
        hunt = lambda name: {"status": "ok", "domain": "georgeromney.example", "personals": []}  # noqa: E731
        found, _ = sl.resolve(row, site("George Romney Ltd, estate agents"), hunt)
        self.assertIsNone(found)
        found, _ = sl.resolve(row, site("George Romney Ltd. Registered number 00321426"), hunt)
        self.assertEqual((found["source"], found["grade"]), ("hunter_company_search", "verified"))
        self.assertEqual(found["hunter"]["domain"], "georgeromney.example")

    def test_dead_site_is_not_accepted(self):
        found, tried = sl.resolve(ROW, site("", status="unreachable_http_0"), None)
        self.assertIsNone(found)
        self.assertFalse(tried[0]["live"])


class FakeDb:
    def __init__(self, row):
        self.row = dict(row)

    def select(self, table, **p):
        return [self.row]

    def patch(self, table, filters, payload):
        self.row.update(payload)
        return [self.row]

    def set_outcome(self, cn, outcome, reason=None):
        self.row.update(outcome=outcome, reason=reason)


class Commands(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb(ROW)
        nx.build_bundle = lambda db, row, campaign, check, **kw: {"company_number": row["company_number"], "website": row["website"]}

    def set(self, text, evidence="", status="ok"):
        nx.scrape_site = site(text, status)
        return sl.cmd_set(self.db, argparse.Namespace(company_number="00321426", url="https://kendal.example", evidence=evidence))

    def test_matched_site_is_recorded_and_bundle_rebuilt(self):
        out = self.set("Registered in England 321426")
        self.assertEqual(out["bundle"]["website"], "https://kendal.example")
        self.assertEqual(self.db.row["raw"]["_site"]["source"], "web_search")
        self.assertEqual(self.db.row["domain"], "kendal.example")

    def test_unmatched_site_refused_without_evidence(self):
        with self.assertRaises(SystemExit) as cm:
            self.set("Romney Marsh Wools")
        self.assertIn("different company", str(cm.exception))
        self.assertIsNone(self.db.row["website"])

    def test_unmatched_site_accepted_with_evidence_and_flagged(self):
        self.set("Kendal Mint Cake since 1918", evidence="Site names Romney's as the maker, same Mintsfeet Road address")
        self.assertEqual(self.db.row["raw"]["_site"]["grade"], "unverified")
        self.assertTrue(self.db.row["raw"]["_site"]["evidence"])

    def test_dead_url_refused(self):
        with self.assertRaises(SystemExit):
            self.set("", status="unreachable_http_0")

    def test_none_sets_outcome_and_needs_the_searches(self):
        with self.assertRaises(SystemExit):
            sl.cmd_none(self.db, argparse.Namespace(company_number="00321426", searched="none"))
        out = sl.cmd_none(self.db, argparse.Namespace(company_number="00321426", searched="name + Kendal, name + LA9 6NA"))
        self.assertEqual(self.db.row["outcome"], "no_site_found")
        self.assertIn("next", out)

    def test_only_the_company_in_hand(self):
        self.db.row["outcome"] = "pending"
        with self.assertRaises(SystemExit):
            self.set("Registered in England 321426")


if __name__ == "__main__":
    unittest.main()

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["OUTREACH_STATE_DIR"] = _TMP
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import argparse  # noqa: E402

import deliver  # noqa: E402
import next as nx  # noqa: E402
import run_state as rs  # noqa: E402

T0 = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)


class FakeDb:
    """companies_seen only, enough of PostgREST for next.py and deliver.py."""

    def __init__(self, n=40, no_website=()):
        self.clock = T0
        self.rows = [
            {"company_number": f"{i:08d}", "company_name": f"Co {i}", "campaign_id": "c1", "csv_order": i,
             "website": None if i in no_website else f"co{i}.example", "domain": f"co{i}.example",
             "email": None, "outcome": "pending", "reason": None, "last_checked_at": None}
            for i in range(1, n + 1)
        ]

    def tick(self):
        self.clock += timedelta(seconds=1)
        return self.clock.isoformat()

    def select(self, table, **p):
        if table == "campaigns":
            return [{"id": "c1", "name": "t", "icp_id": "home-turf-fmcg-v1"}]
        if table == "contacts":
            return []
        assert table == "companies_seen", table
        rows = self.rows
        if "company_number" in p:
            rows = [r for r in rows if r["company_number"] == p["company_number"].removeprefix("eq.")]
        oc = p.get("outcome", "")
        if oc.startswith("eq."):
            rows = [r for r in rows if r["outcome"] == oc[3:]]
        elif oc.startswith("in.("):
            rows = [r for r in rows if r["outcome"] in oc[4:-1].split(",")]
        if "last_checked_at" in p:
            since = p["last_checked_at"].removeprefix("gte.")
            rows = [r for r in rows if r["last_checked_at"] and r["last_checked_at"] >= since]
        key = "last_checked_at" if p.get("order", "").startswith("last_checked_at") else "csv_order"
        rows = sorted(rows, key=lambda r: r[key] or "")
        return rows[: int(p["limit"])] if "limit" in p else rows

    def patch(self, table, filters, payload):
        row = next(r for r in self.rows if r["company_number"] == filters["company_number"].removeprefix("eq."))
        row.update(payload)
        return [row]

    def set_outcome(self, cn, outcome, reason=None):
        row = next(r for r in self.rows if r["company_number"] == cn)
        row.update(outcome=outcome, last_checked_at=self.tick())
        if reason is not None:
            row["reason"] = reason

    def outcome(self, cn):
        return next(r for r in self.rows if r["company_number"] == cn)["outcome"]


def ns(cn, **kw):
    return argparse.Namespace(company_number=cn, **kw)


class Loop(unittest.TestCase):
    def setUp(self):
        for f in Path(_TMP).rglob("*.json"):
            f.unlink()
        self.built = []
        nx.build_bundle = lambda db, row, campaign, check, **kw: self.built.append(row["company_number"]) or {
            "company_number": row["company_number"], "company_name": row["company_name"],
            "website": row.get("website"), "tried": kw.get("tried")}
        nx.scrape_site = lambda url, verify=False: {"status": "unreachable_http_0", "final_url": url}
        nx.hunt_company = lambda name: {"status": "ok", "domain": None}
        nx.fetch_html = lambda url: (0, url, "")
        self.db = FakeDb()

    def step(self, target=None):
        return nx.step(self.db, target, None, now=self.db.clock)

    def finish(self, out, how):
        cn = out["bundle"]["company_number"]
        if how == "send":
            self.db.set_outcome(cn, "promoted_to_contacts", "x")
        elif how == "reject":
            deliver.cmd_reject(self.db, ns(cn, reason="Subsidiary of Big Group per their site"))
        else:
            deliver.cmd_hold(self.db, ns(cn, question="Is a farm shop with a bakery in scope?"))

    def test_one_company_per_call_and_no_queue_size(self):
        out = self.step(3)
        self.assertEqual(set(out), {"bundle"})
        self.assertEqual(out["bundle"]["company_number"], "00000001")
        self.assertEqual(sum(r["outcome"] == "in_research" for r in self.db.rows), 1)

    def test_unfinished_company_is_handed_out_again_not_skipped(self):
        first = self.step(3)
        for _ in range(5):
            again = self.step()
            self.assertEqual(again["bundle"], first["bundle"])
            self.assertIn("note", again)
        self.assertEqual(self.built, ["00000001"])
        self.assertEqual(self.db.outcome("00000002"), "pending")

    def test_stops_at_target_delivered_rejects_do_not_count(self):
        out = self.step(2)
        for how in ("reject", "send", "hold", "send"):
            self.assertIn("bundle", out)
            self.finish(out, how)
            out = self.step()
        self.assertTrue(out["stop"])
        self.assertEqual(out["why"], "target_reached")
        self.assertEqual(out["delivered"], 2)
        self.assertEqual(out["rejected_research"][0]["reason"], "Subsidiary of Big Group per their site")
        self.assertEqual(out["held_for_adam"][0]["question"], "Is a farm shop with a bakery in scope?")
        self.assertEqual(self.db.outcome("00000005"), "pending")
        self.assertTrue(self.step()["stop"])
        self.assertEqual(self.db.outcome("00000005"), "pending")

    def test_reject_streak_stops_the_run_and_new_target_resumes(self):
        out = self.step(5)
        for _ in range(rs.MAX_REJECT_STREAK):
            self.finish(out, "reject")
            out = self.step()
        self.assertEqual(out["why"], "reject_streak")
        self.assertEqual(len(out["rejected_research"]), rs.MAX_REJECT_STREAK)
        self.assertEqual(sum(r["outcome"] == "pending" for r in self.db.rows), 40 - rs.MAX_REJECT_STREAK)
        self.assertIn("bundle", self.step(5))

    def test_a_send_breaks_the_streak(self):
        out = self.step(9)
        for i in range(rs.MAX_REJECT_STREAK * 2):
            self.finish(out, "send" if i % 3 == 2 else "reject")
            out = self.step()
            self.assertIn("bundle", out)

    def test_repeating_target_mid_run_keeps_the_count(self):
        out = self.step(2)
        self.finish(out, "send")
        out = self.step(2)
        self.finish(out, "send")
        self.assertEqual(self.step(2)["why"], "target_reached")

    def test_idle_run_is_abandoned_and_same_target_starts_fresh(self):
        out = self.step(2)
        self.finish(out, "send")
        self.db.clock += timedelta(hours=4)
        self.assertEqual(self.step()["why"], "no_active_run")
        out = self.step(2)
        self.finish(out, "send")
        self.assertIn("bundle", self.step())

    def test_no_website_row_is_handed_out_never_rejected(self):
        self.db = FakeDb(n=2, no_website=(1,))
        out = self.step(5)
        self.assertEqual(out["bundle"]["company_number"], "00000001")
        self.assertIsNone(out["bundle"]["website"])
        self.assertEqual(self.db.outcome("00000001"), "in_research")
        self.assertFalse(any(r["outcome"] == "rejected_ingest" for r in self.db.rows))

    def test_pending_can_run_out(self):
        self.db = FakeDb(n=1)
        out = self.step(5)
        self.finish(out, "send")
        self.assertEqual(self.step()["why"], "no_pending")

    def test_email_domain_site_is_recorded_when_it_matches(self):
        self.db = FakeDb(n=1, no_website=(1,))
        self.db.rows[0].update(email="office@sultan.example", raw={"Postcode": "BL6 4SB"})
        nx.scrape_site = lambda url, verify=False: {"status": "ok", "final_url": "https://www.sultan.example/",
                                                    "_text": "Unit 4b Cranfield Road, Bolton BL6 4SB"}
        out = self.step(1)
        row = self.db.rows[0]
        self.assertEqual(out["bundle"]["website"], "https://www.sultan.example/")
        self.assertEqual(row["domain"], "sultan.example")
        self.assertEqual(row["raw"]["_site"]["grade"], "verified")
        self.assertEqual(row["raw"]["_site"]["source"], "endole_email_domain")

    def test_no_site_found_counts_toward_the_streak(self):
        import site_lookup as sl
        self.db = FakeDb(n=20, no_website=range(1, 21))
        out = self.step(5)
        for _ in range(rs.MAX_REJECT_STREAK):
            cn = out["bundle"]["company_number"]
            sl.cmd_none(self.db, ns(cn, searched="name + town, name + postcode"))
            out = self.step()
        self.assertEqual(out["why"], "reject_streak")
        self.assertEqual(len(out["no_site_found"]), rs.MAX_REJECT_STREAK)

    def test_report_shows_seconds_in_hand(self):
        out = self.step(1)
        self.db.clock += timedelta(seconds=90)
        self.finish(out, "send")
        rep = self.step()
        self.assertEqual(rep["target"], 1)
        self.assertEqual(rep["time_in_hand"][0]["outcome"], "promoted_to_contacts")
        self.assertGreaterEqual(rep["time_in_hand"][0]["seconds"], 0)

    def test_bare_next_without_a_run(self):
        self.assertEqual(self.step()["why"], "no_active_run")


class InHandGuards(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb(n=3)
        self.db.set_outcome("00000001", "in_research")

    def test_reject_and_hold_refuse_a_company_not_in_hand(self):
        for cmd, kw in ((deliver.cmd_reject, {"reason": "Subsidiary of Big Group"}), (deliver.cmd_hold, {"question": "Is this one in scope?"})):
            with self.assertRaises(SystemExit):
                cmd(self.db, ns("00000002", **kw))
        self.assertEqual(self.db.outcome("00000002"), "pending")

    def test_vague_reason_is_refused(self):
        with self.assertRaises(SystemExit):
            deliver.cmd_reject(self.db, ns("00000001", reason="not a fit"))
        self.assertEqual(self.db.outcome("00000001"), "in_research")

    def test_send_refuses_a_company_with_no_website(self):
        self.db.rows[0]["website"] = None
        with self.assertRaises(SystemExit) as cm:
            deliver.cmd_send(self.db, ns("00000001", email="a@b.co"))
        self.assertIn("no website on record", str(cm.exception))

    def test_send_refuses_a_company_never_handed_out(self):
        with self.assertRaises(SystemExit) as cm:
            deliver.cmd_send(self.db, ns("00000002", email="a@b.co"))
        self.assertIn("send refused", str(cm.exception))

    def test_requeue(self):
        deliver.cmd_hold(self.db, ns("00000001", question="Is this one in scope?"))
        deliver.cmd_requeue(self.db, ns("00000001"))
        self.assertEqual(self.db.outcome("00000001"), "pending")
        self.db.set_outcome("00000003", "promoted_to_contacts")
        with self.assertRaises(SystemExit):
            deliver.cmd_requeue(self.db, ns("00000003"))


if __name__ == "__main__":
    unittest.main()

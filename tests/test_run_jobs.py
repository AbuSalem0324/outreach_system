import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("OUTREACH_STATE_DIR", tempfile.mkdtemp())
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import deliver  # noqa: E402
import next as nx  # noqa: E402
import run  # noqa: E402
import run_state as rs  # noqa: E402
from test_next_loop import FakeDb, ns  # noqa: E402

SEQUENCE_WORDS = ("next.py", "run.py", "target", "queue", "batch", "how many", "next company", "remaining", "campaign")


class OneJobPerCompany(unittest.TestCase):
    def setUp(self):
        for f in Path(os.environ["OUTREACH_STATE_DIR"]).rglob("*"):
            if f.is_file():
                f.unlink()
        self.db = FakeDb()
        nx.build_bundle = lambda db, row, campaign, check, **kw: {
            "company_number": row["company_number"], "company_name": row["company_name"], "website": row.get("website")}
        self.jobs = []
        self.in_hand_during_job = []

    def job(self, plan):
        """A stand-in for one Hermes session. plan: company_number -> what the model does."""
        def run_job(cn, prompt, attempt):
            self.jobs.append((cn, attempt, prompt))
            self.in_hand_during_job.append([r["company_number"] for r in self.db.rows if r["outcome"] == "in_research"])
            self.db.tick()
            what = plan.get(cn, "send")
            if what == "send":
                self.db.set_outcome(cn, "promoted_to_contacts", "x")
            elif what == "reject":
                deliver.cmd_reject(self.db, ns(cn, reason="Subsidiary of Big Group per their site"))
            elif what == "walk_away_once" and attempt == 2:
                self.db.set_outcome(cn, "promoted_to_contacts", "x")
            return 0
        return run_job

    def work(self, target, plan=None):
        return run.work(self.db, target, None, job=self.job(plan or {}), step=nx.step, now=lambda: self.db.clock)

    def test_each_company_is_its_own_job_and_only_one_is_ever_in_hand(self):
        rep = self.work(3, {"00000002": "reject"})
        self.assertEqual(rep["why"], "target_reached")
        self.assertEqual(rep["delivered"], 3)
        self.assertEqual([cn for cn, _, _ in self.jobs], ["00000001", "00000002", "00000003", "00000004"])
        self.assertTrue(all(len(x) == 1 for x in self.in_hand_during_job))
        self.assertEqual(self.db.outcome("00000005"), "pending")

    def test_the_job_prompt_holds_one_company_and_no_sign_of_a_sequence(self):
        self.work(2)
        for cn, _, prompt in self.jobs:
            self.assertIn(cn, prompt)
            others = [c for c, _, _ in self.jobs if c != cn]
            self.assertFalse(any(o in prompt for o in others))
            low = prompt.lower()
            for word in SEQUENCE_WORDS:
                self.assertNotIn(word, low, word)

    def test_next_company_is_not_fetched_until_this_one_has_an_outcome(self):
        rep = self.work(1, {"00000001": "walk_away_once"})
        self.assertEqual([(cn, a) for cn, a, _ in self.jobs], [("00000001", 1), ("00000001", 2)])
        self.assertIn("left without an outcome", self.jobs[1][2])
        self.assertEqual(rep["delivered"], 1)
        self.assertEqual(self.db.outcome("00000002"), "pending")

    def test_job_that_never_decides_is_held_for_adam_and_the_run_moves_on(self):
        rep = self.work(1, {"00000001": "walk_away"})
        self.assertEqual(self.db.outcome("00000001"), "held_review")
        self.assertEqual(rep["held_for_adam"][0]["company_number"], "00000001")
        self.assertEqual(rep["delivered"], 1)
        self.assertEqual(self.db.outcome("00000002"), "promoted_to_contacts")

    def test_stop_file_ends_the_run_before_the_next_company(self):
        def plan_job(cn, prompt, attempt):
            self.db.tick()
            self.db.set_outcome(cn, "promoted_to_contacts", "x")
            run.STOP_FILE.write_text("stop")
            return 0
        rep = run.work(self.db, 5, None, job=plan_job, step=nx.step, now=lambda: self.db.clock)
        self.assertEqual(rep["why"], "stopped")
        self.assertEqual(rep["delivered"], 1)
        self.assertEqual(self.db.outcome("00000002"), "pending")

    def test_report_text_for_telegram(self):
        text = run.format_report(self.work(2, {"00000001": "reject"}))
        self.assertIn("Delivered 2 of 2.", text)
        self.assertIn("Rejected in research (1):", text)
        self.assertIn("Subsidiary of Big Group per their site", text)
        self.assertNotIn("—", text)


class NothingTellsTheModelAboutTheSequence(unittest.TestCase):
    def test_card(self):
        low = (ROOT / "research-card.md").read_text(encoding="utf-8").lower()
        for word in SEQUENCE_WORDS:
            self.assertNotIn(word, low, word)

    def test_next_has_no_command_line(self):
        self.assertEqual(nx.main(), 2)

    def test_finishing_commands_say_done_not_what_comes_after(self):
        for name in ("deliver.py", "site_lookup.py", "pick.py"):
            src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn("NEXT_CMD", src, name)
            self.assertNotIn("scripts/next.py", src, name)


if __name__ == "__main__":
    unittest.main()

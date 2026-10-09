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


class Status(unittest.TestCase):
    def setUp(self):
        for f in Path(os.environ["OUTREACH_STATE_DIR"]).rglob("*"):
            if f.is_file():
                f.unlink()
        self.now = rs.utcnow()

    def run_file(self, stopped=None):
        stamp = self.now.isoformat()
        rs.save_run({"campaign_id": "c1", "target": 3, "started_at": stamp, "touched_at": stamp, "stopped": stopped})

    def test_idle(self):
        self.assertEqual(run.status_info()["state"], "idle")

    def test_alive_names_the_company_and_minutes(self):
        from datetime import timedelta
        self.run_file()
        run.PID_FILE.write_text(str(os.getpid()))
        run.note_in_hand(company_number="00715514", company_name="H.Whittaker & Sons", attempt=1,
                         started_at=(self.now - timedelta(minutes=7)).isoformat(), job_pid=os.getpid())
        info = run.status_info(now=self.now)
        self.assertEqual(info["state"], "researching")
        self.assertIn("Alive. Researching H.Whittaker & Sons (00715514), 7 min so far.", info["say"])

    def test_dropped_when_the_worker_is_gone_and_no_report_was_made(self):
        self.run_file()
        run.PID_FILE.write_text("999999999")
        run.note_in_hand(company_number="00715514", company_name="H.Whittaker & Sons", attempt=1, started_at=self.now.isoformat())
        info = run.status_info(now=self.now)
        self.assertEqual(info["state"], "dropped")
        self.assertIn("crashed or was killed", info["say"])
        self.assertIn("H.Whittaker & Sons was in hand", info["say"])

    def test_finished_run_says_why(self):
        self.run_file(stopped="target_reached")
        info = run.status_info(now=self.now)
        self.assertEqual(info["state"], "finished")
        self.assertIn("Target reached.", info["say"])

    def test_in_hand_file_is_cleared_between_jobs(self):
        db = FakeDb()
        nx.build_bundle = lambda d, row, c, ch, **kw: {"company_number": row["company_number"], "company_name": row["company_name"]}
        seen = []

        def job(cn, prompt, attempt):
            seen.append(run.status_info(now=db.clock)["in_hand"])
            db.tick()
            db.set_outcome(cn, "promoted_to_contacts", "x")
            return 0
        run.PID_FILE.write_text(str(os.getpid()))
        run.work(db, 2, None, job=job, step=nx.step, now=lambda: db.clock)
        self.assertEqual([h["company_number"] for h in seen], ["00000001", "00000002"])
        self.assertFalse(run.IN_HAND_FILE.exists())


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

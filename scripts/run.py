#!/usr/bin/env python3
"""/next: the run. One company, one separate research job, start to finish.

  run.py start --target N [--campaign ID]   start a run in the background
  run.py stop                                finish the company in hand, then stop
  run.py status                              is a run going

This script owns the sequence. For each company it starts a NEW Hermes
session with a prompt that contains the research card and that one
company, and waits for it to end. The research job is never told there
is a run, a target, a queue, or a next company. The next company is not
even looked up until this one has an outcome in the database.

When the run stops, this script (not a model) posts the report to
Telegram.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import run_state as rs
from common import Supabase, Telegram, load_env, log, research_card

REPO = Path(__file__).resolve().parents[1]
PID_FILE = rs.STATE_DIR / "run.pid"
STOP_FILE = rs.STATE_DIR / "run.stop"
JOBS_DIR = rs.STATE_DIR / "jobs"
LOGS_DIR = rs.STATE_DIR / "logs"

# One research job. {job} is the prompt file. --ignore-rules keeps Hermes'
# saved memory and skills out, so nothing from earlier jobs leaks in.
# --yolo is needed because nobody is there to approve a command.
HERMES_CMD = os.environ.get(
    "OUTREACH_HERMES_CMD",
    "hermes chat --oneshot -Q --yolo --ignore-rules --source outreach-job --max-turns 80 --in {repo} --query-file {job}",
)
JOB_TIMEOUT_S = int(os.environ.get("OUTREACH_JOB_TIMEOUT_S", "2700"))
ATTEMPTS = 2

JOB_HEAD = "One job: research the company below and finish it with exactly one command from the card.\n\n"
JOB_RETRY = (
    "\n\nThis company has been looked at once already and was left without an outcome. "
    "It still needs exactly one finishing command from the card.\n"
)


def job_prompt(bundle: dict[str, Any], retry: bool = False) -> str:
    return (
        JOB_HEAD + research_card() + "\n===== COMPANY (JSON) =====\n"
        + json.dumps(bundle, indent=2, ensure_ascii=False) + (JOB_RETRY if retry else "") + "\n"
    )


def hermes_job(company_number: str, prompt: str, attempt: int) -> int:
    """Run one research job in a fresh Hermes session. Returns its exit code."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    job = JOBS_DIR / f"{company_number}.txt"
    job.write_text(prompt, encoding="utf-8")
    cmd = [part.format(repo=str(REPO), job=str(job)) for part in shlex.split(HERMES_CMD)]
    out = LOGS_DIR / f"job-{company_number}-{attempt}.log"
    with out.open("w", encoding="utf-8") as fh:
        try:
            return subprocess.run(cmd, cwd=REPO, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                                  timeout=JOB_TIMEOUT_S).returncode
        except subprocess.TimeoutExpired:
            return 124
        except OSError as exc:
            fh.write(f"could not start Hermes: {exc}\n")
            return 127


def outcome_of(db: Any, company_number: str) -> str | None:
    rows = db.select("companies_seen", company_number=f"eq.{company_number}", select="outcome", limit="1")
    return rows[0]["outcome"] if rows else None


def work(db: Any, target: int, campaign: str | None, job: Callable[[str, str, int], int] = hermes_job,
         step: Callable[..., dict[str, Any]] | None = None, now: Callable[[], Any] = rs.utcnow) -> dict[str, Any]:
    """The loop. Returns the stop report."""
    if step is None:
        import next as nx
        step = nx.step
    first = True
    while True:
        if STOP_FILE.exists():
            return stop_now(db, "stopped")
        out = step(db, target if first else None, campaign, now=now())
        first = False
        if out.get("stop"):
            return out
        bundle = out["bundle"]
        cn = bundle["company_number"]
        code = 0
        for attempt in range(1, ATTEMPTS + 1):
            code = job(cn, job_prompt(bundle, retry=attempt > 1), attempt)
            log("job=ended", company_number=cn, attempt=attempt, exit=code, outcome=outcome_of(db, cn))
            if outcome_of(db, cn) != "in_research":
                break
            bundle = rs.cached_bundle(cn) or bundle  # a site may have been recorded on the first pass
        else:
            # Nothing may stay in hand: the run cannot move on until this company has an outcome.
            why = {124: "the research job ran out of time", 127: "Hermes could not be started"}.get(code, f"the research job ended (exit {code})")
            db.set_outcome(cn, "held_review", f"{why} without choosing an outcome, twice. Log: {LOGS_DIR}/job-{cn}-{ATTEMPTS}.log")
            log("guardrail=job_without_outcome", company_number=cn, exit=code)
            if code == 127:
                return stop_now(db, "hermes_missing")


def stop_now(db: Any, why: str) -> dict[str, Any]:
    import next as nx

    run = rs.load_run()
    rows = nx.run_rows(db, run) if run else []
    if run:
        run["stopped"] = why
        rs.save_run(run)
    return rs.report(run, rows, why)


def format_report(rep: dict[str, Any]) -> str:
    lines = [f"{rep['summary']}", f"Delivered {rep['delivered']} of {rep['target']}."]

    def block(title: str, items: list[Any], key: str | None = None) -> None:
        if not items:
            return
        lines.append("")
        lines.append(f"{title} ({len(items)}):")
        for it in items:
            if isinstance(it, dict):
                lines.append(f"- {it['company']} ({it['company_number']}): {it.get(key) or ''}".rstrip(": "))
            else:
                lines.append(f"- {it}")

    block("Drafts delivered", rep["delivered_companies"])
    block("Awaiting your pick", rep["awaiting_pick"])
    block("Held for you", rep["held_for_adam"], "question")
    block("Held on verification", rep["held_verify"], "reason")
    block("Failed verification", rep["rejected_verify"], "reason")
    block("Rejected in research", rep["rejected_research"], "reason")
    block("No website found", rep["no_site_found"], "searched")
    if rep.get("skipped_by_script"):
        lines.append("")
        lines.append(f"Skipped by the script (contact history): {rep['skipped_by_script']}")
    return "\n".join(lines)[:3900]


# ---------------------------------------------------------------------------
# start / stop / status
# ---------------------------------------------------------------------------


def running_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def cmd_start(args: argparse.Namespace) -> int:
    if args.target is None or args.target <= 0:
        raise SystemExit("say how many drafts: run.py start --target <n>")
    if running_pid():
        print(json.dumps({"started": False, "say": "A run is already going. Its report will arrive when it stops. /stop ends it after the current company."}))
        return 1
    if not shutil.which(shlex.split(HERMES_CMD)[0]):
        raise SystemExit(f"cannot find `{shlex.split(HERMES_CMD)[0]}` on PATH; set OUTREACH_HERMES_CMD")
    rs.STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.unlink(missing_ok=True)
    logfile = LOGS_DIR / f"run-{time.strftime('%Y%m%d-%H%M%S')}.log"
    cmd = [sys.executable, str(Path(__file__).resolve()), "work", "--target", str(args.target)]
    if args.campaign:
        cmd += ["--campaign", args.campaign]
    with logfile.open("w") as fh:
        # Its own session, so it outlives the chat turn that started it.
        proc = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    PID_FILE.write_text(str(proc.pid))
    time.sleep(3)
    if proc.poll() is not None:
        # Died straight away: say so now, rather than promise drafts that will never come.
        PID_FILE.unlink(missing_ok=True)
        tail = logfile.read_text(errors="replace").strip().splitlines()[-3:]
        print(json.dumps({"started": False, "log": str(logfile), "say": "The run could not start: " + " | ".join(tail)}))
        return 1
    print(json.dumps({
        "started": True, "target": args.target, "log": str(logfile),
        "say": f"Run started for {args.target} drafts. Each draft arrives here as it is ready, and a report follows when the run stops. Nothing more for you to do.",
    }))
    return 0


def cmd_work(args: argparse.Namespace) -> int:
    load_env()
    PID_FILE.write_text(str(os.getpid()))
    tg = Telegram()
    try:
        Supabase()  # fail before the first company, not after it
        rep = work(Supabase(), args.target, args.campaign)
        tg.send_text(format_report(rep))
        log("run=ended", why=rep["why"], delivered=rep["delivered"])
        return 0
    except Exception as exc:  # noqa: BLE001
        log("run=crashed", error=repr(exc))
        tg.send_text(f"The outreach run stopped on an error: {exc!r}. Any company in hand will be picked up by the next run.")
        raise
    finally:
        PID_FILE.unlink(missing_ok=True)
        STOP_FILE.unlink(missing_ok=True)


def cmd_stop(_: argparse.Namespace) -> int:
    if not running_pid():
        print(json.dumps({"say": "No run is going."}))
        return 0
    rs.STATE_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text("stop")
    print(json.dumps({"say": "The run will stop once the company in hand is finished, then report."}))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(json.dumps({"running": bool(running_pid()), "run": rs.load_run()}, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="the /next run: one research job per company")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("start", "work"):
        s = sub.add_parser(name)
        s.add_argument("--target", type=int)
        s.add_argument("--campaign")
    sub.add_parser("stop")
    sub.add_parser("status")
    args = p.parse_args()
    return {"start": cmd_start, "work": cmd_work, "stop": cmd_stop, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

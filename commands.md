# commands.md: The Telegram Surface

Everything Adam does happens in the Hermes Telegram chat. He types
commands as `o/ next 5`, `o/ status`, `o/ stop`, because Telegram
swallows a leading `/`. Treat `o/ <command>` and `/<command>` alike.
Three kinds
of input: a file, a slash command, a reaction. Hermes maps each to the
scripts below. Research is done by separate one-off jobs that `run.py`
starts, each given only `research-card.md` and one company. The
other markdown files are reference for Adam, not run-time reading.

## A CSV file

An Endole export dropped into the chat starts a new campaign. Hermes:

1. Saves the file locally, runs
   `python3 scripts/ingest.py <file> --name "<caption or filename>"`.
   Pass `--icp <icp_id>` if the caption names one; otherwise the
   active ICP from `icp-definitions.md`.
2. Replies with the summary the script prints: rows, new companies,
   seen before, missing website, missing email, campaign id.

The same file twice is rejected by hash. A different export with
overlapping companies is fine; overlaps are marked `seen_before` and
skipped by `/next` unless asked otherwise.

## `/next [n]` / `outreach n`

Deliver `n` successful first-touch drafts from the most recent campaign
(or `--campaign <id>`). `n` is the only cap. There is no daily ceiling.

Hermes in this chat does one thing:

```
python3 scripts/run.py start --target <n> [--campaign <id>]
```

and replies with the `say` line it prints. That is the whole of its
part. It does not research anything.

`run.py` then works in the background, one company at a time:

1. It takes the next pending company and builds the bundle: Endole
   row, site summary, Companies House officers, Hunter emails,
   `check.md` decision. Hard stops are excluded here.
2. It starts a **new, separate Hermes session** whose whole prompt is
   `research-card.md` plus that one company. That session is a one-off
   job. It is not told there is a run, a target, a queue, or a next
   company, and it carries no memory from the job before.
3. The job ends with one outcome: `deliver.py send`, `pick.py offer`,
   `deliver.py reject`, `deliver.py hold`, or `site_lookup.py none`.
4. Only when that company has an outcome in the database does `run.py`
   look up the next one.
5. When the run stops, `run.py` itself posts the report here:
   delivered, awaiting pick, held with each question, rejected with
   each reason, no website found.

A company with no website in the export is not rejected. The script
tries the Endole email's domain, Hunter by company name, and a web
search of its own, checking each against the company number, postcode
and registered name. Failing that, the research job searches and
records the result with `site_lookup.py set`, or ends on
`site_lookup.py none`.

What the scripts enforce, whatever the model does:

- One company in hand at a time. The next is not fetched until this
  one has an outcome.
- A job that ends without an outcome is run once more; after that the
  company is held for Adam, so nothing is skipped silently.
- `next.py` cannot be run from a command line, so a research job
  cannot pull another company.
- `reject`, `hold` and `site_lookup.py` only work on the company in
  hand. `send` is refused while it has no website on record.
- A site the script cannot match to the company needs `--evidence`,
  and the draft's caption says the site was not matched.
- The run stops at `n` delivered, when pending runs out, or after 8
  rejections, holds or no-site outcomes in a row. `/next` again
  carries on.
- Only one run at a time.

Each of those logs a `guardrail=` line when it bites. Logs are in
`/root/outreach/logs`: one per run, one per research job.

If `n` is omitted, ask for it. Do not assume 10.

## `/stop`

`python3 scripts/run.py stop`. The run finishes the company in hand,
then stops and reports. `python3 scripts/run.py status` says whether a
run is going.

## `o/to <company_number> <n or email>`

Resolves a picker. Hermes:

1. `python3 scripts/pick.py resolve --company-number <n> <choice>`
2. The script prints the card and the chosen recipient. Hermes writes
   the relevance sentence and calls `deliver.py send` with that
   `--email` and the stored angle. `deliver.py` builds the email.

If only one company is `awaiting_pick`, `<company_number>` may be
omitted. Do not draft until this command.

## Held companies: `o/ answer`, `o/ drop`

A research job that cannot decide parks the company with a question.
`o/ status` lists them. Adam settles each one of two ways:

- `o/ answer <company_number> <his answer>` runs
  `python3 scripts/deliver.py answer --company-number <n> --note "<his
  answer, in his words>"`. The company goes back to `pending` with the
  answer attached, and the next research job sees it and acts on it.
- `o/ drop <company_number> [why]` runs
  `python3 scripts/deliver.py drop --company-number <n> --reason
  "<why>"`. The company is out (`rejected_research`, reason prefixed
  `Adam:`).

If Adam answers a held question in plain words without the command,
work out which of the two he means and run it. If it is not clear
which company or which way, ask. Reply with the `say` line.

## `/requeue <company_number>`

`python3 scripts/deliver.py requeue --company-number <n>`. Puts a held
or wrongly rejected company back to `pending`, so the next run picks
it up. Held companies and their questions show in `/status`.

## `/followups`

`python3 scripts/followups.py` lists every contact with a follow-up
due and posts what `followup.md` says is due: an email draft for touch
2 or 3, a LinkedIn task alongside touch 3 when a URL is stored (that
task goes to the LinkedIn bot, not this chat), a
letter task, a call task, or a close when nothing is left to send.
`--list` only lists. It does not send, insert, or close. Nothing is
sent without a reaction. Report emails, LinkedIn tasks, letters,
calls, and closes separately.

## `/replied <email>`, `/dnc <email>`, `/unsub <email>`, `/close <email>`

`python3 scripts/status.py <verb> <email>`. Manual flips, since Zoho is
outside the system. `unsub` also stamps `unsubscribed_at`. `close` ends
a sequence without marking anything permanent.

## `/check <email>`

`python3 scripts/check.py <email>`. One-off history lookup for a
company Adam brings up outside a campaign.

## `/status`

Whether a run is alive, and what it is doing. Lead the reply with
the `run.say` line, word for word: it says alive (and which company,
for how many minutes), finished, or dropped without a report. Then
companies held for Adam, quota used today, drafts awaiting a reaction, follow-ups due, open
sequences. `python3 scripts/status.py summary`.

## Reactions

👍 on a draft file: sent via Zoho, log it. 👎 on a first-touch draft:
reviewed, not sending (`skipped`). 👎 on a follow-up email draft:
sequence over (`closed`). 👎 on a task skips that task only. 🤝 on a
task is a reply. Anything else is ignored. Detail in `send-and-log.md`.

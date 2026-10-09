# commands.md: The Telegram Surface

Everything Adam does happens in the Hermes Telegram chat. Three kinds
of input: a file, a slash command, a reaction. Hermes maps each to the
scripts below. For `/next` and `o/to` the only document Hermes reads
is `research-card.md`, which the scripts print with the work. The
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

The loop is in `next.py`, not in Hermes. One company per call.

1. `python3 scripts/next.py --target <n> [--campaign <id>]` starts the
   run and prints `research-card.md`, then one JSON bundle: Endole row,
   site summary, Companies House officers, Hunter emails, `check.md`
   decision. Hard stops are already excluded by the script.
2. Hermes follows the card for that one company. It does not open
   `research.md`, `draft.md`, or `icp-definitions.md`.
3. One outcome for that company:
   - `python3 scripts/deliver.py send ...` when Stage 3 picked one
     relevant personal or fell through to generic,
   - `python3 scripts/pick.py offer --company-number <n> --file <json>`
     when more than one personal and no single relevant title,
   - `python3 scripts/deliver.py reject --company-number <n>
     --reason "<why>"`,
   - `python3 scripts/deliver.py hold --company-number <n>
     --question "<what Adam needs to decide>"` when in doubt.
4. `python3 scripts/next.py` (no arguments) for the next company. Back
   to step 2, until it prints a stop report instead of a bundle.
5. Reply once with the stop report: delivered, awaiting pick, held for
   Adam with each question, held on verification, rejected in research
   with each reason. Do not narrate the work.

A company with no website in the export is not rejected. The script
tries the Endole email's domain, then Hunter by company name, and
checks each against the company number, postcode and registered name.
If neither holds up, Hermes searches the web and records the result
with `scripts/site_lookup.py set`, or `site_lookup.py none` if there
is nothing to find (`no_site_found`, listed in the stop report).

What the script enforces, whatever Hermes does:

- A company handed out and not finished is handed out again. There is
  no skipping ahead.
- `reject` and `hold` only work on the company in hand.
- `send` is refused while the company has no website on record.
- A site the script cannot match to the company needs `--evidence`,
  and the draft's caption says the site was not matched.
- The run stops at `n` delivered, when pending runs out, or after 8
  rejections, holds or no-site outcomes in a row. Typing `/next` again carries on.
- Hermes is not told how many companies are left.

Each of those logs a `guardrail=` line to stderr when it bites.

If `n` is omitted, do not assume 10 and do not drain the campaign.
If pending is gone before `n` drafts, say so and stop. Don't research
a company that is not in a bundle.

## `o/to <company_number> <n or email>`

Resolves a picker. Hermes:

1. `python3 scripts/pick.py resolve --company-number <n> <choice>`
2. The script prints the card and the chosen recipient. Hermes writes
   the relevance sentence and calls `deliver.py send` with that
   `--email` and the stored angle. `deliver.py` builds the email.

If only one company is `awaiting_pick`, `<company_number>` may be
omitted. Do not draft until this command.

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

Companies held for Adam, quota used today, drafts awaiting a reaction, follow-ups due, open
sequences. `python3 scripts/status.py summary`.

## Reactions

👍 on a draft file: sent via Zoho, log it. 👎 on a first-touch draft:
reviewed, not sending (`skipped`). 👎 on a follow-up email draft:
sequence over (`closed`). 👎 on a task skips that task only. 🤝 on a
task is a reply. Anything else is ignored. Detail in `send-and-log.md`.

# commands.md: The Telegram Surface

Everything Adam does happens in the Hermes Telegram chat. Three kinds
of input: a file, a slash command, a reaction. Hermes maps each to the
scripts below and reads the relevant markdown before doing anything
that needs judgement.

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

1. `python3 scripts/next.py [--campaign <id>] --limit <still needed>`
   prints a JSON bundle per candidate: Endole row, site summary, Companies
   House officers, Hunter emails, `check.md` decision. Candidates with
   a hard stop are already excluded by the script. `--limit` is this
   slice, not the run. After rejects, holds, and picks, call it again
   until `n` drafts have been delivered or no pending rows remain.
2. For each bundle, Hermes runs `research.md` (and `draft.md` only
   once the send target is known).
3. Per candidate, one of:
   - `python3 scripts/deliver.py send ...` when Stage 3 picked one
     relevant personal or fell through to generic,
   - `python3 scripts/pick.py offer --company-number <n> --file <json>`
     when more than one personal and no single relevant title,
   - `python3 scripts/deliver.py reject --company-number <n>
     --reason "<why>"`.
4. Reply once, when the run stops: delivered, awaiting pick, held on
   verification, rejected in research. Do not narrate the work.

If `n` is omitted, do not assume 10 and do not drain the campaign.
If pending is gone before `n` drafts, say so and stop. Don't research
a company that is not in a bundle.

## `o/to <company_number> <n or email>`

Resolves a picker. Hermes:

1. `python3 scripts/pick.py resolve --company-number <n> <choice>`
2. Reads `draft.md`, writes the body for that address (first-name
   greeting if personal), `deliver.py send` with that `--email`.

If only one company is `awaiting_pick`, `<company_number>` may be
omitted. Do not draft until this command.

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

Quota used today, drafts awaiting a reaction, follow-ups due, open
sequences. `python3 scripts/status.py summary`.

## Reactions

👍 on a draft file: sent via Zoho, log it. 👎 on a first-touch draft:
reviewed, not sending (`skipped`). 👎 on a follow-up email draft:
sequence over (`closed`). 👎 on a task skips that task only. 🤝 on a
task is a reply. Anything else is ignored. Detail in `send-and-log.md`.

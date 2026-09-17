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

## `/next [n]`

Fill today's remaining first-touch quota from the most recent campaign
(or `--campaign <id>`). `n` caps it lower than the quota if given.

1. `python3 scripts/next.py [--campaign <id>] [--limit n]` prints a
   JSON bundle per candidate: Endole row, site summary, Companies
   House officers, `check.md` decision. Candidates with a hard stop
   are already excluded by the script.
2. For each bundle, Hermes runs `research.md` and then `draft.md`.
3. Per candidate, one of:
   - `python3 scripts/deliver.py send --company-number <n> --email <e>
     --buyer-name "<name or empty>" --buyer-role "<role>"
     --angle "<one sentence>" --subject "<s>" --body-file <path>`
     which verifies the email, inserts the contact, and sends the draft
     file to Telegram, or
   - `python3 scripts/deliver.py reject --company-number <n>
     --reason "<why>"`.
4. Reply with a one-line tally: delivered, held on verification,
   rejected in research.

If quota is already zero, say so and stop. Don't research anyway.

## `/followups`

`python3 scripts/followups.py` lists every contact with a follow-up
due, builds the templated touch from `followup.md`, sends one file per
contact, and reports the count. `--list` only lists. Nothing sends
without a 👍.

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

👍 on a draft file: sent via Zoho, log it. 👎: reviewed, not sending
(first touch → `skipped`, follow-up → `closed`). Anything else is
ignored. Detail in `send-and-log.md`.

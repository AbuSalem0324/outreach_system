# objective.md: Outreach Pipeline v2

DataBard cold outreach, run from Telegram, executed by Hermes on the
Vultr VPS, sent by hand through Zoho. This file is the north star, short
on purpose. Everything else does one job and defers back here for what
"done" and "never" mean.

## What a completed cycle looks like

A first touch is complete when a `contacts` row reaches `contacted`
(Adam reacted 👍, the email went out via Zoho, `messages` holds the
verbatim copy) or `skipped` (reviewed, deliberately not sent). A
sequence is complete when the third touch is logged, or the contact
replies, unsubscribes, or Adam closes it with 👎 on a follow-up. A draft
that never gets a reaction just sits. Nothing times out, escalates, or
auto-sends.

## Read order

1. `commands.md`: what Adam can type and what each command triggers
2. `icp-definitions.md`: what a good candidate looks like inside a
   batch Endole already filtered, and what disqualifies one
3. `ingest.md`: CSV in, campaign out
4. `check.md`: contact history gate
5. `research.md`: buyer, angle, disqualify
6. `verify.md`: deliverability gate
7. `draft.md`: voice, structure, delivery
8. `followup.md`: the templated second and third touch
9. `send-and-log.md`: the reaction that becomes a database write
10. `schema.md`: reference, the deployed database

## Non-negotiables

These hold regardless of which stage is running. No exception clause.

- **10 first touches a day, maximum.** A ceiling, not a target.
  Follow-ups are on top, they never count against it.
- **Three touches, then stop.** Day 0, +3 days, +7 more days. The
  database trigger sets `next_due_at`; nothing else does.
- **Follow-ups are on demand.** They surface when Adam runs
  `/followups`, never pushed unasked.
- **Follow-ups are templated.** Only the original angle from the first
  touch is slotted in. No new research, no regenerated copy.
- **Dedup on `email`, never `domain`.** A second person at a company
  already reached is not blocked. The same address is.
- **Three permanent hard stops**: `unsubscribed`, `do_not_contact`,
  `replied`. Once set, that email never re-enters outreach through any
  route. `log_contact` refuses to overwrite them.
- **Every sent email carries a working, pre-filled unsubscribe link**:
  `https://www.databard.net/unsubscribe?e=recipient@email.com`. Never
  a placeholder, on follow-ups as much as first touches.
- **No invented specifics.** Every claim traces to the Endole row, the
  company's own site, Companies House, or a plain web search result.
- **No parrot mode.** Research informs relevance, it doesn't get
  recited. If the email only makes sense once you explain where the
  data came from, it doesn't ship.
- **Research can disqualify.** Passing the Endole filter is not the
  same as being a buyer. A company that turns out to be a subsidiary,
  a consultancy, in administration, or already tooled up gets
  `rejected_research` with a reason, not a weak email.
- **Buyers, not consultancies.** Boutique consultancies are out.
- **Replies are manual.** Zoho is outside this system. Adam tells
  Hermes `/replied`, `/dnc`, `/unsub`. Nothing infers them.
- **Voice**: UK spelling, sentence case, no em dashes, no hashtags, no
  buzzwords, no AI cadence, no dashboards or generic BI framing. Detail
  in `draft.md`.

## What this system is not

Not automated sending. Not a CRM beyond three touches and a status.
Not inbox-aware. Not multi-ICP at once. Each of those is a deliberate
absence, add them only once this is boring and stable.

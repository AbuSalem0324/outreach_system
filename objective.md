# objective.md: Outreach Pipeline v2

DataBard cold outreach, run from Telegram, executed by Hermes on the
Vultr VPS, sent by hand through Zoho. This file is the north star, short
on purpose. Everything else does one job and defers back here for what
"done" and "never" mean.

## What a completed cycle looks like

A first touch is complete when a `contacts` row reaches `contacted`
(Adam reacted 👍, the email went out via Zoho, `messages` holds the
verbatim copy) or `skipped` (reviewed, deliberately not sent). A
sequence is complete when the fourth touch resolves, or there is nothing
left to send it through, or the contact replies on any channel,
unsubscribes, or Adam closes it. A draft or task that never gets a
reaction just sits. Nothing times out, escalates, or auto-sends.

## Read order

For Adam, and for anyone changing the system. Hermes does not read
these at run time: during `/next` and `o/to` it works from
`research-card.md` alone, printed by the scripts with each bundle.
When a rule changes in `research.md`, `draft.md`, or
`icp-definitions.md`, change the card too.

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

- **No daily delivery ceiling.** The number Adam types is the only cap.
  `outreach 10` means 10 successful draft deliveries this run. Rejects,
  holds, and picks do not count. Follow-ups never count toward it.
  Stop when that many drafts are in the chat, or no pending rows remain.
  `next.py` does the counting and hands out one company at a time; a
  long streak of rejections also stops the run, for Adam to look at.
  Do not invent a daily 10.
- **Four touches, then stop.** Emails at day 0, +3, +7. LinkedIn
  alongside touch 3, if a URL was stored. Letter, then call, as touch
  4. Timing comes from the trigger, plus `resolve_touch` for the
  letter-to-call gap. Nothing else writes `next_due_at`.
- **Follow-ups are on demand.** They surface when Adam runs
  `/followups`, never pushed unasked. Tasks included.
- **Follow-ups are templated.** Only the original angle from the first
  touch is slotted in. No new research, no regenerated copy. That
  covers the letter and the call prompt too.
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
  Hermes `/replied`, `/dnc`, `/unsub`. Nothing infers them. A 🤝 on a
  task is the same hard stop as `/replied`.
- **Hard stops apply to every channel.** `unsubscribed`,
  `do_not_contact`, and `replied` block email, LinkedIn, letter, and
  phone.
- **Calls: Corporate TPS always.** TPS as well when `phone_type` is
  `mobile`. The task says so. This system does not check for him, and
  it does not dial.
- **Letters carry the same pre-filled unsubscribe link** as every
  email. Envelope address is printed, not handwritten: real stamp, no
  window, no logo. Signed in ink.
- **No automated LinkedIn actions. No auto-dialling.**
- **Voice**: UK spelling, sentence case, no em dashes, no hashtags, no
  buzzwords, no AI cadence, no dashboards or generic BI framing. Detail
  in `draft.md`.

## What this system is not

Not automated sending. Not a CRM beyond four touches and a status.
Not inbox-aware. Not multi-ICP at once. Each of those is a deliberate
absence, add them only once this is boring and stable.

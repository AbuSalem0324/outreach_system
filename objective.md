# objective.md — Outreach Pipeline

DataBard cold outreach, running through Hermes on the Vultr VPS, drafts
reviewed and sent manually by Adam. This file is the north star, short
on purpose, everything else in this repo does one job well and defers
back to this one for what "done" and "never" mean.

## What a completed cycle looks like

One outreach cycle ends when a `contacts` row reaches either
`status = 'contacted'` (Adam reacted ✅ on Telegram, actually sent via
Zoho) or `status = 'skipped'` (reviewed, deliberately not sent). Nothing
in this system sends on its own. A draft that never gets a reaction just
sits as `new`, it does not time out, escalate, or auto-send.

## Read order

1. `icp-definitions.md` — which ICP is active, what it targets, why
2. `find.md` — discovery, deterministic first, AI only on survivors
3. `check.md` — contact history gate before anything gets drafted
4. `research.md` — buyer identification and the one grounded angle
5. `verify.md` — email deliverability, universal gate before drafting
6. `draft.md` — voice, structure, delivery format
7. `send-and-log.md` — the reaction that turns a human decision into a
   database write
8. `schema.md` — reference, the actual deployed database, checked
   against reality, not reconstructed from what other files claim

## Non-negotiables

These hold regardless of which stage is running. Nothing downstream
overrides them, no exception clause, no "just this once."

- **10 sends a day, maximum.** Not a target to hit, a ceiling.
- **Dedup on `email`, never `domain`.** A second contact at a company
  already reached is not automatically blocked, a second attempt at the
  same address is.
- **Three permanent hard stops**: `unsubscribed`, `do_not_contact`,
  `replied`. Once any of these is set, that email never re-enters
  automated outreach again, through any route, no matter how much later
  or how the candidate resurfaces.
- **Every sent email carries a working, pre-filled unsubscribe link**:
  `https://www.databard.net/unsubscribe?e=recipient@email.com`, never a
  placeholder.
- **No invented specifics.** Every claim in a draft traces to something
  actually observed, Companies House, the company's own site. Nothing
  assumed to sound more researched.
- **No parrot mode.** Research informs relevance, it doesn't get
  recited. An email that only makes sense once you explain where the
  data came from doesn't ship.
- **Buyers, not consultancies.** Boutique consultancies are explicitly
  out, they've never converted and are no longer worth the send.
- **Voice**: UK spelling, sentence case, no em dashes, no hashtags, no
  buzzwords, no AI-sounding mechanical patterns, no dashboards or
  generic BI framing. Full detail lives in `draft.md` and the DataBard
  voice guide, this is the reminder, not the source.

## What this system is not yet

Not automated sending, every send is a human decision. Not a CRM in the
full sense, no pipeline stages beyond first contact, no deal tracking,
that's deliberate, this is an outreach engine, not a sales system. Not
multi-ICP simultaneously, ICP B stays inactive until ICP A has a real
reply-rate baseline to compare against.

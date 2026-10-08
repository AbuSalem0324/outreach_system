# DataBard Outreach v2

Cold outreach pipeline for DataBard, driven entirely from Telegram.
Adam drops an Endole CSV into the chat, Hermes on the Vultr VPS
researches each company, drafts one email per candidate, and hands the
draft back as a file. Every send is a manual decision, confirmed with a
reaction. Follow-ups are templated from the original angle and only
surface when Adam asks for them. Nothing here sends on its own.

Start at `objective.md`. It holds the non-negotiables and the read
order. Every other file does one job and defers to it. If anything here
conflicts with `objective.md`, that file is right, fix the other one.

Hermes pulls this repo from GitHub at the start of every run. The repo
is the source of truth, not whatever is cached on the box. Pulling is
not reading: the one document Hermes reads during a run is
`research-card.md`, and the scripts print it.

## Files

- `objective.md`: north star, non-negotiables, read order
- `commands.md`: the Telegram surface: what Adam types, what happens
- `icp-definitions.md`: the character of a good candidate within an
  already-filtered batch, plus explicit disqualifiers
- `ingest.md`: Endole CSV in, campaign and `companies_seen` rows out
- `check.md`: contact history gate before drafting
- `research-card.md`: the one page Hermes works from at run time;
  a condensed copy of the three files below, kept in step by hand
- `research.md`: buyer, angle, and the disqualify path
- `verify.md`: email deliverability gate before drafting
- `draft.md`: voice, structure, Telegram delivery format
- `followup.md`: touches two to four, including LinkedIn, letter, and call tasks
- `send-and-log.md`: reaction-triggered logging, first touch and follow-up
- `schema.md`: the deployed Supabase schema, checked against the database

## Scripts

Deterministic parts only. Judgement (research, drafting) is Hermes,
reading the markdown above.

- `scripts/common.py`: env loading, Supabase and Telegram helpers
- `scripts/ingest.py`: CSV to `campaigns` and `companies_seen`
- `scripts/next.py`: assemble research bundles for the `--limit` slice
- `scripts/hunter.py`: Hunter.io domain-search (fetch only)
- `scripts/pick.py`: Telegram recipient picker when Stage 3 is ambiguous
- `scripts/check.py`: contact history decision for one email
- `scripts/verify.py`: MillionVerifier decision for one email
- `scripts/first_touch.py`: the fixed first-touch copy and the checks
  on the generated sentences
- `scripts/deliver.py`: build the email, insert the contact, send the
  draft file, or record a research rejection
- `scripts/followups.py`: build and deliver due follow-ups on demand
- `scripts/status.py`: manual status flips (replied, dnc, unsub, closed)
- `scripts/send_and_log_listener.py`: reaction handler

## Infrastructure this assumes

- Supabase project **CRM** (`pmbzagybwcwhcmlrkrbu`), RLS on, secret-key
  access only
- Hermes agent on a Vultr VPS, credentials in its own `.env`, never here
- Telegram bot with `message_reaction` in `allowed_updates`
- Zoho Mail, manual sends
- MillionVerifier, email deliverability
- Companies House public API, officer lookups
- `databard.net/unsubscribe` on Vercel

Environment variables the scripts expect: `SUPABASE_URL`,
`SUPABASE_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`COMPANY_HOUSE`, `MILLIONVERIFIER_API_KEY`, `HUNTER_API_KEY`.

No credentials, API keys, or client data live in this repository.

# DataBard Outreach

Cold outreach pipeline for DataBard. Sourcing, research, and drafting
run through Hermes on the Vultr VPS; every send is a manual decision by
Adam, confirmed via a Telegram reaction. Nothing here sends on its own.

Start at `objective.md`. It holds the non-negotiables that apply
regardless of which file you're in, and the order the rest are meant to
be read in. Every other file here does one job and defers back to it,
if anything here ever conflicts with `objective.md`, that file is
right, fix the other one.

## Files

- `objective.md` — north star, non-negotiables, read order
- `icp-definitions.md` — active targeting definition(s), versioned for
  A/B comparison
- `find.md` — discovery, deterministic first, AI only on survivors
- `check.md` — contact history gate before drafting
- `research.md` — buyer identification, one grounded angle per candidate
- `verify.md` — email deliverability gate before drafting
- `draft.md` — voice, structure, Telegram delivery format
- `send-and-log.md` — reaction-triggered send confirmation and logging
- `schema.md` — the actual deployed Supabase schema, checked against
  the database, not reconstructed from what other files say

## Reading this cold

Any agent, human or otherwise, picking this repo up without prior
context should read `objective.md` first, then follow its read order.
Don't start mid-pipeline, the non-negotiables in `objective.md` aren't
repeated in every file that depends on them.

## Infrastructure this assumes

- Supabase project **CRM** (`pmbzagybwcwhcmlrkrbu`), RLS on, secret-key
  access only
- Vercel project `databard-website`, serving `databard.net` (unsubscribe
  route) and `databard.xyz`
- Hermes agent on a Vultr VPS, credentials in its own `.env`, never in
  this repo
- Zoho Mail, manual sends
- MillionVerifier, email deliverability checks

No credentials, API keys, or client data live in this repository at any
point. If something here ever needs one, it goes in an environment
variable on whichever machine actually calls it, not in a file that gets
committed.

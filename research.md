# research.md — Per-Candidate Research

Runs on the shortlist that's already cleared `check.md`, typically a
handful of names, not a wide net. This is deliberately deeper than
`find.md`'s Stage 5 AI pass: at this point token cost is no longer the
constraint, accuracy and specificity are.

Objective: produce, for each candidate, an actual named buyer where
possible, and one genuinely specific angle grounded in evidence, not a
generic template with the company name dropped in.

## Hard rule: no invented specifics

Every claim used in the eventual email must trace back to something
actually observed: a Companies House record, the company's own published
site content, or a filing trend. Nothing gets assumed or invented to
sound more personalised. If no genuine angle can be found for a
candidate, that's a signal to skip it, not a reason to write generic
copy dressed up as research.

## Stage 1: buyer identification (script plus light judgement)

Two legitimate sources, no LinkedIn scraping:

- Companies House officers endpoint: real director/PSC names, free,
  official data, no terms-of-service restriction.
- The company's own team or about page, already scraped in `find.md`'s
  Stage 3, re-checked here if that page wasn't present at find time.

Match against the active ICP's `buyer_titles`. Prefer an officer or
team-page entry whose title lines up with Operations Director, Supply
Chain Manager, Head of Operations, MD, or Finance Director. Where the
two sources disagree, common when a company hasn't updated its officer
register, prefer the site's current team page for the name actually
used, since that's what's true today.

No confident name emerges: fall back to a role-addressed opener. Never
invent a name.

## Stage 2: the angle (judgement, grounded in evidence)

Read what `find.md` already gathered (SIC match, accounts-type trend,
scraped keyword hits, BI-tool absence) plus the site's own content, and
pick one sharp, true observation to open with.

Good angle: something the company's own material actually shows, a
recent move from micro to small filing, a site describing multi-site
operations, an about page describing manual stock processes.

Bad angle: a generic industry statistic that could apply to any company
in the sector.

One angle per candidate, not a list. Nothing specific enough surfaces:
that's a legitimate reason to drop the candidate rather than force a
weak opener.

## Stage 3: email confidence

If `find.md` flagged the buyer's email `unverified` (constructed from a
pattern, not found published), this is the point to decide whether it's
used as-is or held back. Verifying it, SMTP ping or a verification API,
is still an open decision, not yet built into this pipeline. Until
that's decided, `unverified` emails get flagged clearly in the handoff
to `draft.md` rather than treated the same as a confirmed one.

## Output

Appended to the candidate's row in `contacts.notes`, no new table:
buyer name and title (or "role-addressed, no confident name"), the one
chosen angle, and the email confidence level. This is what `draft.md`
reads to write the actual email.

## What this stage does not do

No drafting, no decisions on tone or structure, that belongs to
`draft.md`, which also owns the mandatory unsubscribe link and the
voice rules. No touching of send status. The only output is the
research summary that makes `draft.md`'s job possible to do well
instead of generically.

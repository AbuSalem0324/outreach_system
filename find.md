# find.md — Lead Discovery

Reads the `active` ICP from `icp-definitions.md`. Produces up to the day's
remaining quota (10/day cap, set in `objective.md`) of qualified candidates,
landed in `contacts` with `status = 'new'`. Spends AI tokens only on
candidates that survive every deterministic filter first — this is the whole
point of the stage.

Runs as a daily job. Stops as soon as quota is filled; does not need to
exhaust the search space every run.

---

## Constraint that shapes this entire pipeline

Google Places API terms license `place_id` for indefinite caching. Every
other field in a Places response (name, address, rating, the `website`
field itself) is licensed for temporary display only — their terms
specifically name "creating mailing lists or telemarketing lists based on
the Content" as a prohibited use.

Practical effect: Places is a live lookup, not a database. Nothing from a
Places response is written to storage except `place_id`. The moment a
`website` URL is in hand, this pipeline moves on to Stage 2 and treats
everything from there on as independently obtained — Companies House is
Open Government Licence data with no such restriction, and a company's own
website is their own published content, not Google's.

---

## Stage 0 — Skip already-evaluated candidates

Before querying Places, check `places_seen` for the `place_id` (if from a
prior run) or `domain` (if reached some other way). If `outcome` is
anything other than `pending`, skip — it's already been through this
pipeline once, no need to re-spend Companies House rate limit or scrape
time on it. Log every new candidate to `places_seen` immediately on first
sight, `outcome = 'pending'`, so a run that crashes partway doesn't
reprocess what it already touched.

## Stage 1 — Discovery (script, Places API)

For each `sic_codes` category in the active ICP, construct free-text Places
Text Search queries combining the category's plain-English term with each
`geography.primary` region (e.g. "food manufacturer Leeds", "wholesale
food distributor Yorkshire"). Paginate each query.

For each result: extract `place_id` and `website` only. Discard everything
else from the response immediately, per the constraint above.

- No `website` field → reject, `outcome = 'rejected_no_website'`. Can't
  research or email a business with no site.
- Has a website → proceed to Stage 2.

## Stage 2 — Companies House cross-reference (script, official API)

Resolve the candidate's domain to a Companies House entry — search by
company name derived from the site's own `<title>` / `og:site_name` (not
from Places' `name` field), or by matching the registered office postcode
if the site publishes one.

Filter against the active ICP:

- `company_status` must be `active` — otherwise `rejected_status`.
- `accounts.accounts_type` must NOT be in
  `icp.company_size_band.companies_house_accounts_type_exclude`
  (`micro-entity`, `dormant`) — otherwise `rejected_size`. This is an
  exclude filter, not a match filter: Companies House's accounts_type
  field describes filing regime, not company size, and the field
  cannot reliably distinguish "small" from "medium" from "somewhat
  larger" within everything that isn't micro or dormant. Don't treat
  it as a size gate beyond ruling out those two extremes.
- Declared `sic_codes` must intersect the ICP's `sic_codes` list — this is
  the authoritative sector match, more precise than any Places category.
  No intersection → `rejected_sic`.

No CH match found at all (sole traders, unincorporated, or a data gap) —
don't auto-reject. Flag for the AI stage to make the call from site content
alone rather than silently dropping legitimate small businesses that
happen not to resolve cleanly.

Survivors get `charges` and `filing history trend` pulled too (available,
not filtered on) — this rides along to Stage 4's scoring as a soft signal,
not a hard gate.

## Stage 3 — Own-site scrape (script, no AI)

Fetch homepage + about/contact/team/careers pages if present. Extract,
deterministically:

- Company display name (title tag / og:site_name)
- Any published email (`mailto:` regex)
- Team/careers page presence (size proxy)
- Keyword hits against a fixed term list derived from the ICP's sector
  (manual reporting, spreadsheets, forecasting-adjacent language)
- BI/dashboard embed signatures in page source (Power BI, Tableau, Looker)
  — presence suggests they've already solved this, deprioritise; absence
  combined with visibly dated reporting language is a positive signal

## Stage 4 — Composite deterministic score

Combine into one number, no AI involved:

- SIC match: exact category hit scores higher than adjacent-category hit
- Accounts-type: passed the exclude filter (not micro, not dormant) —
  this is a pass/fail input from Stage 2, not itself a scoring
  dimension, don't try to rank within it, the field can't support that
  distinction
- Site signals: keyword hits + team/careers presence + absence of BI tooling
- Filing trend (soft): micro→small or small→medium movement scores up

Candidates below the cutoff are rejected here, `outcome = 'rejected_sic'`
or similar as appropriate, logged, done — no tokens spent.

## Stage 5 — AI judgment (only survivors reach this)

For each candidate clearing Stage 4's threshold:

1. Read the scraped site text against `icp.pitch_angle` — does this
   company plausibly have the operational complexity and manual-process
   pain the pitch addresses, not just a keyword match but a genuine read.
2. One plain web search on the company name. Companies House and the
   company's own site are both static, neither reliably reflects a
   recent acquisition, closure, or leadership change, and this kind of
   thing routinely surfaces in ordinary search results, trade press,
   corporate finance announcements, local news, without needing a
   targeted query. A recently-acquired subsidiary often doesn't have
   the same buying autonomy an independent SME does, worth knowing
   before treating this as a clean independent-buyer fit, not
   necessarily an auto-reject, just something the fit reasoning in
   Stage 3 below should account for.
3. If no email was found in Stage 3, infer the likely buyer from
   `icp.buyer_titles` using team/about page text, and construct a probable
   address using standard patterns (firstname@domain,
   firstname.lastname@domain). Mark `confidence: unverified` — this does
   not get sent blind.
4. Final fit score. Reject below threshold (`rejected_ai`), log the reason
   in `places_seen` for later review of whether the cutoff is calibrated
   right.

## Stage 6 — Dedup and handoff

Before inserting anything: check the constructed/discovered email against
`contacts.email` (email is the dedup key, not domain — a second contact at
the same company under a different address is not automatically blocked).
If it already exists, do not re-insert; update `places_seen` to
`promoted_to_contacts` if it happens to already be there for tracking
purposes, otherwise leave as `rejected_ai` equivalent — this is a rare
edge case since Stage 1 dedup on `place_id`/`domain` should catch most
repeats earlier.

New email → insert into `contacts`:

- `status = 'new'`
- `source = 'find_pipeline'`
- `domain`, `company_name` from Stage 3
- `notes` — one line: the fit reasoning from Stage 5, plus
  `confidence: unverified` if the email was constructed rather than found
- an `icp_id` tag identifying which ICP sourced this candidate

Update `places_seen.outcome = 'promoted_to_contacts'`.

Stop once today's remaining quota (10 minus anything already contacted
today) is filled, or once the ICP's query space for this run is exhausted,
whichever comes first.

## What happens next

Rows land as `status = 'new'`. `check.md` and `research.md` pick up from
there — this file's job ends at handoff, not at drafting or sending.

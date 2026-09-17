# research.md: Per-Candidate Research

Hermes' job, run on each bundle `next.py` prints. Inputs: the Endole
row (`raw`), the site summary the script scraped, Companies House
officers, the `check.md` decision. Output: a buyer, one angle, and an
email, or a rejection with a reason. Token cost is not the constraint
here, accuracy is.

## Hard rule: no invented specifics

Every claim in the eventual email traces to something observed: the
Endole row, the company's own site, a Companies House record, or a
plain web search result. Nothing assumed to sound more researched. If
no honest angle surfaces, reject the candidate, don't pad.

## Stage 1: does this company survive the disqualifiers?

Read the active ICP's `disqualifiers` in `icp-definitions.md` against
everything in the bundle, plus **one plain web search on the company
name**. The search is not optional: Endole and the site are both
static, and an acquisition, administration, or closure usually shows
up in trade press or local news long before either updates.

Read the registered address in `raw._address` too. A `C/O` address
naming another food company or a group finance director, or an office
park address shared with a known group, is the cheapest subsidiary
signal in the bundle; confirm with the search, then reject.

Any disqualifier hit →
`deliver.py reject --company-number <n> --reason "<one line>"`.
The reason is stored on `companies_seen` and is what a future
campaign sees if the company resurfaces. Be specific: "acquired by X
in 2025 per trade press" beats "not a fit".

Also reject if the `character` list has nothing to hang an angle on.
A company that matches every column but whose site is three pages of
stock photos gives you nothing true to say.

## Stage 2: buyer identification

Sources, in order of trust for what is true today:

1. A named contact in the Endole row with a matching email. Use it
   if the role fits `buyer_titles`.
2. The site's team or about page (in the bundle's `site.people`
   guesses and text excerpt).
3. Companies House officers (in the bundle). Active directors only.
   Prefer one whose role or occupation fits `buyer_titles`. An MD or
   sole director of an SME is usually the right person.

Where sources disagree on a name, the site wins, Companies House lags.
No confident name → role-addressed, never invented.

## Stage 3: the email

In this order, stop at the first that exists:

1. A personal address in the Endole row (`raw._personal_email`, the
   `Email` column when Endole fills it with a named person's address).
2. A personal address for the chosen buyer found on the site or via
   the web search.
3. The generic address from Endole (`raw._generic_email`, or the
   `Email` column when it is `info@`, `sales@`, `reception@`) → role-
   addressed greeting, still worth sending.
4. Construct `firstname@domain` or `firstname.lastname@domain` only if
   the site or search shows that pattern for someone else at the
   company. Otherwise use the generic.

`deliver.py` runs `verify.md` on whatever you pass. Constructed
addresses are held on `catch_all` like anything else, so don't spend
effort on a guess when a published generic exists.

## Stage 4: the angle

One sentence. Grounded in something observed, phrased at the shape of
the thing, not the instance (see `draft.md`, Personalisation ceiling).
It must stand alone as a complete sentence, because `followup.md`
slots it verbatim into the second and third touch after the words
"The short version:". Write it so that reads naturally.

Good: "You're running production and your own fleet from one site,
which is exactly where forecasting and stock planning get complicated
before any software is big enough to be worth buying."

Bad: "Your Companies House filing shows you moved to small company
status last year." (cites the source)

Bad: "Your reporting is currently done by hand every Monday." (a
diagnosis nobody confirmed)

Bad: three true facts in a row. One is an observation, three is a
dossier.

## Output

Passed to `deliver.py send` as arguments: `--email`, `--buyer-name`
(empty string if role-addressed), `--buyer-role`, `--angle`, and the
`--subject` and `--body-file` that `draft.md` produces. `deliver.py`
writes `buyer_name`, `buyer_role`, `angle`, and a short `notes` line
to `contacts`. No separate research table.

## What this stage does not do

No drafting beyond the angle sentence, no sending, no status writes
except through `deliver.py`.

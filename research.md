# research.md: Per-Candidate Research

Hermes' job, run on each bundle `next.py` prints. Inputs: the Endole
row (`raw`), the site summary the script scraped, Companies House
officers, Hunter personals/generics, the `check.md` decision. Output:
a buyer, one angle, and an email, a picker, or a rejection with a
reason. Token cost is not the constraint here, accuracy is.

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

Pool of **personal** addresses, all observed, never invented:

- Hunter `personals` in the bundle
- Endole `raw._personal_email` when it is a named person, not `info@`
- A personal address on the site or in the web search for a named buyer

A personal is **relevant** when title or department fits the ICP
`buyer_titles` (operations, supply chain, MD, finance) or is clearly
the owner-operator. Marketing, HR, sales-dev, and intern roles are
not relevant.

Decision tree, stop at the first hit:

1. **Exactly one relevant personal** → that address is the send
   target. Go straight to Stage 4 and `draft.md`. Greeting uses their
   first name. Do not offer a picker.
2. **More than one personal, and not exactly one relevant** → picker.
   Do not call `deliver.py send`. Write
   `/root/outreach/picks/<company_number>.json` with every personal
   (relevant first), one-line `reason` each, the generic as the last
   item if one exists, plus `angle`, `company_name`, `company_number`.
   Then `python3 scripts/pick.py offer --company-number <n> --file
   <that path>`. Stop this company. Adam replies `o/to <n> <index or
   email>`; then draft to the chosen address.
3. **Else** (no personals, or one personal that is not relevant) →
   generic. Sources, first that exists: Hunter `generics`, Endole
   `raw._generic_email` / `info@` `sales@` `reception@`, a generic on
   the site. Role-addressed greeting. Still worth sending.

Do not construct `firstname@domain` unless the site or search shows
that pattern for someone else at the company. Hunter `pattern` alone
is not enough.

`deliver.py` runs `verify.md` on whatever you pass. Do not verify the
whole Hunter list; only the address that is actually sent.

Picker JSON shape:

```json
{
  "company_number": "01234567",
  "company_name": "Example Ltd",
  "angle": "one complete sentence",
  "candidates": [
    {
      "email": "jane@example.com",
      "name": "Jane Roe",
      "position": "Operations Director",
      "department": "operations",
      "seniority": "executive",
      "confidence": 92,
      "kind": "personal",
      "reason": "ops title, matches buyer_titles"
    }
  ]
}
```

## Stage 4: the angle

One sentence. Grounded in something observed, phrased at the shape of
the thing, not the instance (see `draft.md`, Personalisation ceiling).
It must stand alone as a complete sentence, because `followup.md`
slots it verbatim into the second and third touch after the words
"The short version:". Write it so that reads naturally. Do not put
the bespoke-vs-enterprise pitch in the angle; that is fixed copy in
`draft.md` and `followup.md`.

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

On a straight draft or after `o/to`: passed to `deliver.py send` as
arguments `--email`, `--buyer-name` (empty string if role-addressed),
`--buyer-role`, `--angle`, and the `--subject` and `--body-file` that
`draft.md` produces. `To:` on the contact row is that email. Never
leave it blank and never default it to candidate #1 without a pick.

On a picker: `pick.py offer` sets `companies_seen.outcome` to
`awaiting_pick`. No `contacts` row until `o/to`.

## What this stage does not do

No drafting beyond the angle sentence until the send target is known,
no sending, no status writes except through `deliver.py` or
`pick.py offer`. Hunter does not choose the recipient.

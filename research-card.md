# research-card.md: one company, start to finish

This is the only document Hermes reads during `/next` and `o/to`.
`next.py` and `pick.py resolve` print it with the bundle. The longer
files (`research.md`, `draft.md`, `icp-definitions.md`) are reference
for Adam. If they disagree with this card, tell Adam; do not pick one.

You have one company. Work on that company only, and take the time
it needs: there is no batch, and you are not told how many are left.
You do not write the email: you supply a buyer, an address, an angle,
and one relevance sentence, and `deliver.py` assembles the rest from
fixed copy. Finish with exactly one command from "Finish" below, then
ask `next.py` for the next company. `next.py` decides when the run is
over, not you.

ICP for this card: `home-turf-fmcg-v1`.

## Hard rule

Every claim traces to something observed: the Endole row, the
company's own site, Companies House, or a plain web search result.
Nothing invented, nothing assumed to sound researched. A rejection
needs an observed reason too. "Not a fit" is not a reason.

## 1. Disqualify?

Run one plain web search on the company name. Not optional: an
acquisition, administration, or closure shows up in the press before
Endole or the site updates. Read `raw._address` as well: a `C/O`
address naming another company or a group finance director is a
subsidiary signal; confirm with the search.

Reject only on one of these, with the evidence in the reason:

- Subsidiary or recently acquired: a parent owns the tooling decision
- In administration, liquidation, strike-off, or visibly closing
- A consultancy, agency, broker, or software vendor, whatever the SIC
- Already tooled: Power BI / Tableau / Looker / Qlik embeds, or a
  vendor case study naming them
- A shell, holding company, or property vehicle with no operation
- Site is dead, parked, or abandoned
- Nothing true to hang an angle on (see 4)

A doubt is not a disqualifier. If the evidence is mixed, or you cannot
tell whether one of these applies, hold the company with one question
for Adam. Do not reject it to move on.

What a buyer looks like, none of it required: a physical operation
(production line, cold store, fleet, several sites, shifts), sells to
trade, independent and owner-managed, no visible data stack, roughly
20 to 250 employees.

## 2. Buyer

Titles that fit: Operations Director, Supply Chain Manager, Head of
Operations, Managing Director, Finance Director. An MD or sole
director of an SME is usually right.

Sources, most trusted first:

1. A named contact in the Endole row with a matching email
2. The site's team or about page
3. Companies House officers, active directors only

Where they disagree on a name, the site wins. No confident name means
role-addressed: pass an empty `--buyer-name`. Never invent one.

## 3. Email

Personal addresses, all observed: Hunter `personals`, Endole
`raw._personal_email` when it is a named person, a personal address
on the site or in search for a named buyer.

A personal is relevant when the title fits the list in 2 or the
person is clearly the owner-operator. Marketing, HR, sales-dev, and
interns are not relevant.

Stop at the first hit:

1. Exactly one relevant personal: send to it. No picker.
2. More than one personal, and not exactly one relevant: picker. Do
   not send.
3. Otherwise: a generic. First that exists of Hunter `generics`,
   Endole `raw._generic_email`, a generic on the site. Empty
   `--buyer-name`. Still worth sending.

Do not construct `firstname@domain` unless the site or search shows
that pattern for someone else there. Hunter `pattern` alone is not
enough.

## 4. Angle (`--angle`)

One complete sentence about the shape of their operation. Follow-ups,
the letter, and the call prompt reuse it verbatim, after "The short
version:", so it must stand alone and read naturally there. No pitch
in it.

Good: "You're running production and your own fleet from one site,
which is exactly where forecasting and stock planning get complicated
before any software is big enough to be worth buying."

## 5. Relevance sentence (`--relevance`)

One sentence for the first email. Opens with something like "This
could be useful for <company> because" and builds on the angle. The
fixed offer line follows it automatically; do not restate the offer.

Both sentences fail the same three ways:

- Citing the source: "your filing shows", "I saw on your site"
- A guess stated as fact: "your reporting is done by hand"
- Stacked facts: speak at category level ("production, your own
  fleet, scheduling"), not a list of specifics

UK spelling, sentence case, no em dashes, no buzzwords. If the
sentence reads thin once written this way, reject the company. Do
not pad.

## Address and phone

Only when observed. Omit the flag otherwise.

- `--postal-address`: trading address printed on the company's own
  site. Never the registered office, never `C/O`.
- `--phone-type`, required with `--phone`: `direct` (a named person's
  work line), `switchboard` (company main number), `mobile` (a
  mobile, or anything unclear).
- `--linkedin-url` and `--phone` may come from Hunter on the chosen
  person.

## Finish

Exactly one of these four for this company.

Send:

```
python3 scripts/deliver.py send --company-number <n> --email <e> \
  --buyer-name "<name, or empty for a generic inbox>" \
  --buyer-role "<role>" --angle "<sentence>" --relevance "<sentence>" \
  [--linkedin-url <url>] [--phone <number> --phone-type <type>] \
  [--postal-address "<address>"]
```

If `deliver.py` refuses a sentence, fix that sentence and call it
again. Do not reject the company because a sentence was refused.

Picker: write `/root/outreach/picks/<company_number>.json`, then
`python3 scripts/pick.py offer --company-number <n> --file <path>`.
Every personal, relevant first, the generic last if one exists.

```json
{
  "company_number": "01234567",
  "company_name": "Example Ltd",
  "angle": "one complete sentence",
  "postal_address": "1 Mill Lane, Bolton BL1 1AA",
  "candidates": [
    {"email": "jane@example.com", "name": "Jane Roe",
     "position": "Operations Director", "kind": "personal",
     "confidence": 92, "reason": "ops title, fits buyer titles",
     "linkedin_url": "https://www.linkedin.com/in/example",
     "phone": "+44 161 000 0000", "phone_type": "direct"}
  ]
}
```

Reject:

```
python3 scripts/deliver.py reject --company-number <n> \
  --reason "<which disqualifier, and what you saw>"
```

"Acquired by X in 2025 per trade press" is a reason. "Not a fit" is
not.

Hold, when Adam needs to decide something you cannot:

```
python3 scripts/deliver.py hold --company-number <n> \
  --question "<the one thing Adam needs to decide, and what you saw>"
```

## Then

Run `python3 scripts/next.py`. It prints either the next company or a
stop report. On a stop report, reply to Adam once with what it says
and stop. Do not research a company `next.py` did not give you.

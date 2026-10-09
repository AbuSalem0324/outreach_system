# research-card.md: one company, start to finish

This card is the whole brief. The longer files in this repository
(`research.md`, `draft.md`, `icp-definitions.md`) are reference for
Adam; do not open them.

The job is one company: the one in the JSON below this card. Research
it properly. There is no deadline and nothing waiting behind it, so
take the searches and the reading the company needs. A careful
rejection is as good a result as a draft; a quick guess is not.

You do not write the email: you supply a buyer, an address, an angle,
and one relevance sentence, and `deliver.py` assembles the rest from
fixed copy. The job ends with exactly one command from "Finish".

ICP for this card: `home-turf-fmcg-v1`.

If the JSON has `adam_note`, Adam has already looked at this company
and answered a question about it. His answer settles that question:
act on it, and do not hold the company on the same point again.

## Hard rule

Every claim traces to something observed: the Endole row, the
company's own site, Companies House, or a plain web search result.
Nothing invented, nothing assumed to sound researched. A rejection
needs an observed reason too. "Not a fit" is not a reason.

## 0. No website in the bundle

Only when the bundle has `site_search`. The script has already tried
the Endole email's domain, Hunter, and a web search of its own.
`already_tried` shows each candidate and its `status`:

- `exists_but_blocked_the_script`: the site is there, the script was
  refused. Open it yourself. It is probably the right one.
- `no_answer`: the script got nothing. Open it yourself before you
  believe it; do not write "dead" on the script's word.
- `ok` with grade `unverified` or `plausible`: it loaded but did not
  name this company. Look at it.

Then run your own web searches: the company name with its town, and
with `registered_postcode`. Run them. Copying `already_tried` into
`--searched` is not a search. Then one of:

```
python3 scripts/site_lookup.py set --company-number <n> --url <url>
```

The script loads the site and looks for the company number, postcode,
or registered name. If it accepts, it prints a fresh bundle: carry on
from section 1. If it refuses, the site may belong to a namesake. Try
another result, or add `--evidence "<what on the site ties it to this
company>"` if you can point to something specific. Do not guess.

```
python3 scripts/site_lookup.py none --company-number <n> \
  --searched "<the searches you ran>"
```

when two or three different searches turn up no site of their own. A
directory listing or a Companies House page is not their site. This is
an outcome, not a rejection, and it ends the job.

## 1. Disqualify?

Run one plain web search on the company name. Not optional: an
acquisition, administration, or closure shows up in the press before
Endole or the site updates. Read `raw._address` as well: a `C/O`
address naming another company or a group finance director is a
subsidiary signal; confirm with the search.

Reject when the research shows this is not a company worth writing
to. That judgement is yours, and it is the reason this job is done by
research and not by a mailing list. The usual grounds:

- Subsidiary or recently acquired: a parent owns the tooling decision
- In administration, liquidation, strike-off, or visibly closing
- A consultancy, agency, broker, or software vendor, whatever the SIC
- Already tooled: Power BI / Tableau / Looker / Qlik embeds, or a
  vendor case study naming them
- A shell, holding company, or property vehicle with no operation
- Site is dead, parked, or abandoned
- Nothing true to hang an angle on (see 4)

The list is not closed. If the research turns up another real reason
this company is a poor fit, reject on it. Whatever the ground, the
reason must say what you found, specifically enough that Adam can
agree or overrule it at a glance.

A rejection rests on something found, not on a doubt. If the evidence
is mixed, or you cannot tell, hold the company with one question for
Adam.

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

Exactly one of these four (or `site_lookup.py none` from section 0).

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
Every personal, relevant first, the generic last if one exists. Write
the angle and the relevance sentence now, as for a send: Adam picks
the address and the draft is built from this file with no further
research. `"kind": "generic"` on a shared inbox.

```json
{
  "company_number": "01234567",
  "company_name": "Example Ltd",
  "angle": "one complete sentence",
  "relevance": "one complete sentence",
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

## When the command succeeds

The job is finished. Reply with one line saying what you did, and
stop. If the command was refused, read why, fix that, and run it
again: a refusal is not an outcome.

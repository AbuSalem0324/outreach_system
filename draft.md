# draft.md — Drafting

Runs after `verify.md` confirms a deliverable address. Turns the
candidate's `research.md` summary into an actual, ready-to-send email.

## Delivery: Telegram, one file per candidate

Sent as a Telegram document via Hermes' existing channel, not typed into
the chat as text. A file per candidate keeps the daily review scrollable
by name rather than buried in a wall of pasted messages, which was the
"chat litter" problem this is specifically avoiding.

Filename: `YYYY-MM-DD_companyname.txt`. Contents: subject line, blank
line, body, exactly as it should be pasted into Zoho.

No Drive or Docs layer. Once actually sent, Zoho's own Sent folder is
the permanent, verbatim, timestamped archive, and `contacts.notes`
already carries the structured summary. Duplicating the draft into Drive
would be a second copy of something already covered twice, for real
setup cost and no real gain.

Nothing here gets sent automatically. This is a file waiting for Adam to
read, decide, and manually send.

## Voice rules

From the DataBard voice guide, enforced on every draft:

- UK spelling, sentence case
- No em dashes, no hashtags, no buzzwords
- No AI-sounding mechanical patterns
- Direct, no consultancy jargon
- Positioning by refusal: no dashboards, no generic BI/Power BI framing,
  no generalist "we do everything" language, stay specific to
  forecasting, reporting, and lightweight automation

## Structure

1. **Subject** — specific to the one angle from `research.md`, never a
   generic hook. If the subject could be sent to any company in the
   sector unchanged, it's wrong.
2. **Greeting** — named buyer only if `research.md` found a name that's
   actually tied to the address being sent to. If the email is a shared
   or role inbox (`info@`, `enquiries@`, `sales@`), greet by role or
   drop the name entirely, don't address a shared inbox by a personal
   first name nobody confirmed reads it.
3. **Who DataBard is** — two or three sentences, front-loaded, before
   any relevance argument: data work, custom tool development, and
   automation, closing the gap between manual processes and BI stacks
   that are usually overkill for what a business this size actually
   needs. Roughly consistent across emails, this is identity, not
   personalisation, it doesn't need to be unique per candidate the way
   the relevance paragraph does.
4. **Relevance** — one paragraph, opens with something like "this could
   be useful for [company] because," and gives the actual reasoning.
   Grounded in what `research.md` found, but framed as *why it might
   matter*, not as a claim about their current internal state. See
   Personalisation ceiling below, this is where that rule lives now.
5. **Ask** — low friction. A short call offered, not demanded.
6. **Sign-off**, including the mandatory unsubscribe line.

## Mandatory unsubscribe line

Every email includes, with the actual recipient address populated,
never a placeholder:

```
https://www.databard.net/unsubscribe?e=recipient@email.com
```

## Personalisation ceiling

`research.md` gathers evidence so the relevance paragraph is genuinely
true, not so it gets recited back. Citing the source in the email
itself, "your Companies House filing shows," "I saw your accounts
moved to small company status," "your team page lists 12 staff," reads
as surveillance, not diligence.

There's a second, quieter version of the same failure: stating an
unverified guess about their internal state as fact. "This would be
useful because you're currently stitching this together by hand" is
just as much a fabricated claim as citing a source, it's a diagnosis
nobody confirmed, dressed up as insight. The honest version reasons
about *why it could matter*, given what's actually observed, not what
their process currently is.

**Not this:** "I noticed your recent filing shows you've grown from
micro to small company status, and your website mentions a new
facility."

**Also not this:** "This would be useful because your reporting is
currently stitched together by hand every week." Nobody established
that, it's assumed because it fits the pitch.

**This instead:** "You're running production and your own fleet from
one site, this is exactly the kind of setup where forecasting and
stock planning get complicated fast, and where a proper BI stack would
be overkill for what's actually needed." Grounded in the real
observation, honest that it's reasoning about relevance, not a claim
about their internal reality.

If the relevance paragraph reads thin once it's written this way,
that's a signal to hold the candidate back, the same rule running
through every stage of this pipeline: drop rather than pad with detail
to sound more done.

## What this stage does not do

No sending, no verification (already done in `verify.md`), no contact
logging. Logging only happens in `send-and-log.md`, triggered once Adam
confirms he's actually sent it, not when the draft is generated.

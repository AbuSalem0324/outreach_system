# draft.md — Drafting

Runs after `verify.md` confirms a deliverable address. Turns the
candidate's `research.md` summary into an actual, ready-to-send email.

## Delivery: Telegram, one file per candidate

Sent as a Telegram document via Hermes' existing channel, not typed into
the chat as text. A file per candidate keeps the daily review scrollable
by name rather than buried in a wall of pasted messages, which was the
"chat litter" problem this is specifically avoiding.

Filename: `YYYY-MM-DD_companyname.txt`. Contents:

```
To: recipient@company.com
Subject: [subject line]

[body]
```

`To` first, its own line, before the subject, this is the piece that
was missing, a file with a subject and a body but no visible recipient
means going back to `contacts` to look the address up separately before
you can actually send. The whole point of this delivery format is that
nothing extra needs looking up, copy `To`, `Subject`, and body straight
into Zoho's three fields and go.

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

Four of these six pieces are fixed, the same every time, not written
fresh per email. Only the greeting (mechanical, based on address type)
and the relevance paragraph (must be genuinely per-company) are
generated. Treat the fixed pieces as literal constants Hermes inserts
unchanged, not prose it's instructed to reproduce consistently, that
distinction matters, "write this the same way each time" drifts across
ten separate generations a day in a way a literal constant can't.

1. **Subject** — fixed:

   ```
   Forecasting and reporting for food manufacturers
   ```

   Not personalised per company. Specific-but-parroting subject lines
   were the harder failure mode to hold consistent across AI-generated
   drafts, a fixed line removes it rather than policing it better.
2. **Greeting** — the one piece of this section that's still dynamic,
   because it's mechanically determined by verified data, not creative
   personalisation. Named buyer only if `research.md` found a name
   that's actually tied to the address being sent to. If the email is
   a shared or role inbox (`info@`, `enquiries@`, `sales@`), greet by
   role or drop the name entirely, don't address a shared inbox by a
   personal first name nobody confirmed reads it.
3. **Who DataBard is** — fixed:

   ```
   DataBard does forecasting, reporting, and small automation jobs for
   food manufacturers. Fixed scope, a working output, not a six-month
   software programme. I spent years on the floor at Tesco and on the
   service desk at 2 Sisters, so the work is aimed at how a factory
   actually runs.
   ```
4. **Relevance** — the one genuinely generated paragraph. Opens with
   something like "this could be useful for [company] because," and
   gives the actual reasoning. Grounded in what `research.md` found,
   framed as *why it might matter*, not as a claim about their current
   internal state. See Personalisation ceiling below.
5. **Ask** — fixed:

   ```
   Happy to do a short call if that's useful.
   ```
6. **Closing line** — fixed, replaces what used to be a generated
   "unsubscribe line":

   ```
   Not relevant? Let me know.
   https://www.databard.net/unsubscribe?e=recipient@email.com
   ```

   Softer than "unsubscribe here," invites a reply either way, someone
   can just say "not relevant" instead of clicking through, while the
   link still does the actual compliance work. The unsubscribe page
   itself is unambiguous once clicked, so this phrasing doesn't lose
   clarity, it just doesn't lead with it.

## Unsubscribe requirement

Covered in Structure, item 6, the closing line is fixed and mandatory
on every email, actual recipient address populated, never a
placeholder. Not restated here to avoid the two sections drifting out
of sync with each other.

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

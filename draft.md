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
2. **Opener** — the single grounded observation `research.md` produced,
   written as something a person would notice, not as a cited finding
   (see Personalisation ceiling below). Named buyer if one was found,
   role-addressed if not.
3. **Bridge** — one or two sentences connecting that specific observation
   to what DataBard actually does. Not a service list, not a pitch deck
   in prose.
4. **Ask** — low friction. A short call offered, not demanded.
5. **Sign-off**, including the mandatory unsubscribe line.

## Mandatory unsubscribe line

Every email includes, with the actual recipient address populated,
never a placeholder:

```
https://www.databard.net/unsubscribe?e=recipient@email.com
```

## Personalisation ceiling

`research.md` gathers evidence so the angle is genuinely true, not so
it gets recited back. Citing the source in the email itself, "your
Companies House filing shows," "I saw your accounts moved to small
company status," "your team page lists 12 staff," reads as
surveillance, not diligence. That's the tell that turns a personalised
email into something that sounds like being watched rather than
understood, exactly the parrot-mode failure where an AI hands back
public data dressed up as insight.

Research exists to establish *why* something is relevant, not to be
quoted. Write the observation the way a person would actually notice
it, referring to what the company visibly does or says about itself,
never the mechanism that surfaced it. If a claim only makes sense once
you explain where the data came from, it's not ready to send: either
it can be said as something a person would plausibly just notice, or
the candidate gets dropped, not padded with sourced detail to make it
sound researched.

**Not this:** "I noticed your recent filing shows you've grown from
micro to small company status, and your website mentions a new
facility."

**This instead:** "Looks like things are scaling fast on your end,"
said once, tied straight to the actual ask, not stacked as a list of
findings.

If the angle reads thin once it's written this way, that's a signal to
hold the candidate back, the same rule running through every stage of
this pipeline: drop rather than pad with detail to sound more done.

## What this stage does not do

No sending, no verification (already done in `verify.md`), no contact
logging. Logging only happens in `send-and-log.md`, triggered once Adam
confirms he's actually sent it, not when the draft is generated.

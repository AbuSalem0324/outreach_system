# draft.md: Drafting the First Touch

Hermes' job, after `research.md`, before `deliver.py send`. Turns the
buyer, angle, and email into a ready-to-send file.

## Delivery: Telegram, one file per candidate

`deliver.py` sends the draft as a Telegram document, named
`YYYY-MM-DD_companyname.txt`, contents:

```
To: recipient@company.com
Subject: [subject line]

[body]
```

Copy the three pieces into Zoho and send. Nothing else needs looking
up. Zoho's Sent folder plus the `messages` row are the archive; no
Drive layer.

## Voice rules

- UK spelling, sentence case
- No em dashes, no hashtags, no buzzwords
- No AI cadence: no "I hope this finds you well", no triads, no
  "I noticed that", no "in today's fast-paced"
- Direct, no consultancy jargon
- Positioning by refusal: no dashboards, no generic BI or Power BI
  framing, no "we do everything". Bespoke forecasting, reporting, and
  small automation, fitted to the current workflow. Not another
  platform to learn, and not an enterprise system most of which would
  sit unused.

## Structure

Five fixed pieces, one generated sentence. Fixed pieces are literal constants,
inserted unchanged, not prose Hermes is asked to reproduce
consistently. That distinction is the whole point: "write it the same
each time" drifts across ten drafts a day, a constant doesn't.

1. **Subject**, fixed:

   ```
   Forecasting and reporting for food manufacturers
   ```

   (ICP B, when active, uses `Forecasting and reporting for SMEs`.)

2. **Greeting**, mechanical. `Hi <first name>,` if `research.md`
   tied a name to the address being sent to. `Hi,` for a generic or
   role inbox. Never a first name on `info@`.

3. **Who DataBard is**, fixed:

   ```
   DataBard builds bespoke forecasting, reporting and small automation
   tools for food manufacturers. Fixed scope, a working output, not a
   six-month software programme. I spent years on the floor at Tesco
   and on the service desk at 2 Sisters, so the work is aimed at how a
   factory actually runs.
   ```

4. **Relevance**, two parts. First sentence generated: opens with
   something like "This could be useful for <company> because" and
   builds on the angle from research (the shape of the operation, not
   a diagnosis). Second sentence is a fixed constant, inserted
   unchanged:

   ```
   A small forecasting or reporting tool, built around the current
   workflow, can sit next to how the operation already runs, without
   the learning curve or the cost of an enterprise system most of
   which would go unused.
   ```

   Do not rewrite that second sentence. Do not add a third. The
   generated line carries their context; this line carries the offer.

5. **Ask**, fixed:

   ```
   Happy to do a short call if that's useful.
   ```

6. **Closing**, fixed, recipient address populated:

   ```
   Not relevant? Let me know.
   https://www.databard.net/unsubscribe?e=recipient@email.com
   ```

Sign-off: `Adam` on its own line before the closing block.

## Personalisation ceiling

Three ways the relevance paragraph goes wrong, all landing in "this
person is watching me" rather than "this person understands me".

**Citing the source.** "Your filing shows", "your team page lists",
"I saw on your site". Diligence reads as surveillance the moment you
name where it came from.

**Stating a guess as fact.** "You're stitching this together by hand"
is a diagnosis nobody confirmed. Reason about why it could matter
given what's visible, not about what their process is.

**Stacking true facts.** Four real specifics in one sentence is a
report with the citations removed. Speak at the category level:
"production, your own fleet, routing, scheduling" not "a chilled plant
in Farnworth running seven days a week for wholesalers".

If the generated sentence reads thin once written this way, hold the
candidate back. Drop rather than pad. Do not bulk it out by restating
the fixed offer line in different words.

## Handoff

Write the body to a temp file and call:

```
python3 scripts/deliver.py send --company-number <n> --email <e> \
  --buyer-name "<name or empty>" --buyer-role "<role>" \
  --angle "<sentence>" --subject "<subject>" --body-file <path>
```

`deliver.py` verifies the address, inserts the contact as `new` with
the draft stored on the row, sends the file, and records the Telegram
`message_id`. If verification holds or drops the address, nothing is
inserted and the script says why.

## What this stage does not do

No sending, no logging. Logging happens in `send-and-log.md` on 👍.

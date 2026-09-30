# followup.md: Touches Two to Four

On demand, never pushed. `scripts/followups.py`, no AI. Everything
surfaces when Adam runs `/followups`, and every touch is a manual
action confirmed by a reaction.

## The sequence

| Touch | Due | Channel | Delivered as |
|---|---|---|---|
| 1 | first send | email | draft file, `draft.md` |
| 2 | +3 days | email | draft file, template below |
| 3 | +7 days | email + LinkedIn | draft file, plus a LinkedIn task if `linkedin_url` is set |
| 4a | +7 days | letter | letter task, if `postal_address` is set |
| 4b | +4 days after the letter, or at once if none | phone | call task, if `phone` is set |

## When something is due

`contacts.next_due_at` is set by the trigger `contacts_set_next_due`
whenever `last_contacted_at` moves:

| After touch | `next_due_at` |
|---|---|
| 1 | `last_contacted_at + 3 days` |
| 2 | `last_contacted_at + 7 days` |
| 3 | `last_contacted_at + 7 days` |

The one exception: `resolve_touch` moves `next_due_at` after a letter
decision, so the call lands once the letter has arrived. Nothing else
writes that column.

A contact is due when `status = 'contacted'`, `next_due_at <= now()`,
no draft is waiting (`draft_subject is null`) and no task is pending
(no `messages` row with `outcome = 'pending'`). A draft or task that
never gets a reaction just waits; a second one is not sent.

What `/followups` sends for a due contact:

- `contact_count` 1 or 2: the email draft for touch 2 or 3. At touch 3,
  also a LinkedIn task if `linkedin_url` is set.
- `contact_count` 3, no step-4 letter row: a letter task if
  `postal_address` is set, otherwise straight to the call.
- `contact_count` 3, letter row resolved: a call task if `phone` is
  set. No phone and no letter: the sequence ends as `closed`.

## Email templates

Fixed text. `{angle}` is `contacts.angle` verbatim, `{greeting}` is
`Hi <first name>,` if `buyer_name` is set else `Hi,`, `{company}` is
`company_name`, `{email}` the recipient. Subject reuses the first touch
subject with `Re:` so it threads.

### Touch 2

```
Subject: Re: Forecasting and reporting for food manufacturers

{greeting}

Following up on my note from earlier in the week. The short version:
{angle}

That is the kind of job I build around: a small forecasting or
reporting tool fitted to the current workflow, not another platform
to learn, and cheaper than an enterprise system most of which would
sit unused.

Happy to do a short call if that's useful, or I can send over a
one-page example of the kind of output I mean.

Adam

Not relevant? Let me know.
https://www.databard.net/unsubscribe?e={email}
```

### Touch 3

No longer the last touch, so it no longer says "last one from me".

```
Subject: Re: Forecasting and reporting for food manufacturers

{greeting}

One more note on this. If forecasting or reporting comes up at
{company} at some point, I'm easy to find. Still the same offer: a
tool built for how the work already runs, not a bloated system to
learn. The thinking behind my earlier note still stands: {angle}

Adam

Not relevant? Let me know.
https://www.databard.net/unsubscribe?e={email}
```

## Tasks: LinkedIn, letter, call

Posted as their own Telegram messages, one task per message. LinkedIn
tasks go to the LinkedIn bot (`TELEGRAM_LI_BOT_TOKEN` /
`TELEGRAM_LI_CHAT_ID`). Letter and call tasks stay on the email bot.
Before posting, insert a `messages` row: `channel`, `sequence_step`,
`outcome = 'pending'`, and the Telegram `message_id` as
`telegram_message_id`.

- **LinkedIn** (text message): name, role, company, `linkedin_url`.
  Connection request only, no pitch in the note. Caption:
  `👍 sent / 👎 not sending / 🤝 they responded`.
- **Letter** (document, `YYYY-MM-DD_letter_companyname.txt`): recipient
  name, role, company, `postal_address`, then the letter text. Caption:
  `👍 posted / 👎 no letter, call next / 🤝 they responded`.
- **Call** (text message): name, role, company, `phone`, `phone_type`,
  `angle` as a one-line prompt. Always: check Corporate TPS. If
  `phone_type = 'mobile'`: check TPS too. Caption:
  `👍 called / 👎 not calling / 🤝 we spoke`.

### The letter

Same voice rules as `draft.md`. Shorter than the email: the fixed
"who DataBard is" paragraph, `{angle}` in one line, how to get in
touch. Printed, signed in ink. Envelope address printed, not handwritten: real stamp, no window, no logo.
Ends with the same opt-out as every email:

```
If you'd rather I didn't write again, let me know.
https://www.databard.net/unsubscribe?e={email}
```

Address from `postal_address` only, which comes from the company's
own site. Never the Companies House registered office.

## Reactions

On an email draft, unchanged: 👍 → `log_contact` with the stored
subject and body, 👎 → `status = 'closed'`, sequence over.

On a task, `resolve_touch(message_id, outcome)` does every write:

| Reaction | Outcome | Effect |
|---|---|---|
| 👍 | `done` | Logged. Letter: call due in 4 days. Call: sequence ends, `closed`. |
| 👎 | `skipped` | This task only. Letter: call due now. Call: sequence ends, `closed`. |
| 🤝 | `responded` | `status = 'replied'`, hard stop, Adam owns it from here. |

👎 means different things on a draft and on a task, on purpose: a
declined letter shouldn't kill the call. The caption on every message
says which it is. To end a sequence outright from any point, `/close`.

## What this stage does not do

No research, no regenerated copy, no timing decisions beyond the
trigger and `resolve_touch`, no sending, no automated LinkedIn or
dialling.

# followup.md: Second and Third Touch

Templated, on demand, never pushed. `scripts/followups.py`, no AI.

## When a follow-up is due

`contacts.next_due_at` is set by the database trigger
`contacts_set_next_due` whenever `last_contacted_at` moves:

| After touch | `next_due_at` |
|---|---|
| 1 | `last_contacted_at + 3 days` |
| 2 | `last_contacted_at + 7 days` |
| 3 | null, sequence over |

Any status other than `contacted`, or a non-null `unsubscribed_at`,
nulls it. Nothing else writes that column.

A contact is due when `status = 'contacted'`, `next_due_at <= now()`,
and no draft is already waiting (`draft_subject is null`). If a draft
is waiting and Adam never reacted, it just waits; a second file is not
sent.

## The templates

Fixed text. `{angle}` is `contacts.angle` verbatim, `{greeting}` is
`Hi <first name>,` if `buyer_name` is set else `Hi,`, `{company}` is
`company_name`, `{email}` the recipient. Subject reuses the first
touch subject with `Re:` so it threads in the recipient's inbox.

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

```
Subject: Re: Forecasting and reporting for food manufacturers

{greeting}

Last one from me. If forecasting or reporting comes up at {company}
at some point, I'm easy to find. Still the same offer: a tool built
for how the work already runs, not a bloated system to learn. The
thinking behind my earlier note still stands: {angle}

Adam

Not relevant? Let me know.
https://www.databard.net/unsubscribe?e={email}
```

## Delivery

One Telegram document per due contact, named
`YYYY-MM-DD_followup<step>_companyname.txt`, same `To / Subject /
body` layout as a first touch. The script stores the subject and body
on `contacts.draft_subject` / `draft_body`, records
`telegram_message_id`, stamps `draft_delivered_at`.

## Reactions

👍 → `log_contact` with the stored subject and body: `contact_count`
increments, `messages` gets the row, the trigger sets the next due
date or nulls it after touch 3.
👎 → `status = 'closed'`, draft cleared, sequence over. Not a hard
stop, `check.md` treats `closed` as a flag not a block.

## What this stage does not do

No research, no regenerated copy, no timing decisions beyond the
trigger, no sending.

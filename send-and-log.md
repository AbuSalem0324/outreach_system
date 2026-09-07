# send-and-log.md — Send Confirmation and Logging

Closes the loop. A draft sits on Telegram until Adam reacts to it, the
reaction is the only signal this stage acts on, nothing here runs on a
timer or a guess.

## The two reactions

| Reaction | Meaning | Action |
|---|---|---|
| 👍 | Sent via Zoho | Log the contact, flip to `contacted` |
| 👎 | Reviewed, not sending | Flip to `skipped`, no contact log |

Changed from the original ✅/🗑️ pair, those aren't in Telegram's
default quick-reaction set on every client. 👍/👎 are, and the same
rule still holds, "sent" and "reviewed but rejected" have to be
visibly different reactions, not the same one meaning two things.

## Mechanics

Hermes' Telegram bot listens for `message_reaction` updates
(`message_reaction` must be included in `allowed_updates`, Bot API 7.0+).
Each event gives `message_id`, `old_reaction`, `new_reaction`, and who
reacted, no message content, just the identifier.

On receiving one:

1. Look up `contacts` where `telegram_message_id` matches the reacted
   message's `message_id`.
2. **Idempotency guard**: if that row's `status` is already `contacted`
   or `skipped`, ignore the event. This covers duplicate delivery,
   toggling the reaction off and back on, or reacting twice, none of
   these should double-log a send or flip a decision that's already
   made.
3. `new_reaction` contains 👍, row is still `new` → run `log_contact`
   (the same Postgres function built earlier): email, company_name,
   domain, `source = 'find_pipeline'`, notes carried over from
   `research.md`'s summary. This sets `status = 'contacted'`,
   `last_contacted_at = now()`, bumps `contact_count`.
4. `new_reaction` contains 👎, row is still `new` → update
   `status = 'skipped'` directly, no `log_contact` call, this was
   never actually sent so `contact_count` and `last_contacted_at`
   should not move.
5. Any other reaction, or a reaction on a message with no matching
   `telegram_message_id` (e.g. something outside this system entirely)
   → ignored.

## Tracking a draft from delivery to decision

When `draft.md` sends a file to Telegram, it writes the resulting
`message_id` to `contacts.telegram_message_id` and stamps
`draft_delivered_at`. If the draft gets edited and resent (the in-place
edit workflow already tested), the new message's id overwrites the old
one, the reaction that counts is always on whichever version is
current.

This makes `draft_delivered_at` → `last_contacted_at` (or the move to
`skipped`) a real, queryable gap: how long a draft typically sits before
being acted on, and what fraction of drafts get sent versus skipped.
That second number in particular is worth watching over time, a rising
skip rate is the earliest signal that `find.md`'s scoring or
`research.md`'s angle-finding has drifted from actually producing
sendable candidates, long before reply rate would tell you anything.

## What this stage does not do

No drafting, no research, no verification. It has exactly one job:
turn a human decision, made by reacting to a file, into a database
write. If the reaction never comes, the row simply stays `new`,
nothing times out or auto-sends.

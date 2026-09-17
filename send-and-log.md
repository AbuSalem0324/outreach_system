# send-and-log.md: Reaction to Database Write

Closes the loop. A draft sits on Telegram until Adam reacts. The
reaction is the only signal; nothing runs on a timer.

## The two reactions

| Reaction | On a first touch (`status = 'new'`) | On a follow-up (`status = 'contacted'`) |
|---|---|---|
| 👍 | `log_contact` → `contacted`, touch 1 logged | `log_contact` → count +1, touch logged, next due set |
| 👎 | `status = 'skipped'` | `status = 'closed'` |

Both clear `draft_subject`, `draft_body`, `telegram_message_id` on the
contact. That is the idempotency guard: a second reaction on the same
message finds no matching row and is ignored.

## Mechanics

Production path is the Hermes plugin `send-and-log` on
`gateway_platform_event`; the gateway already long-polls Telegram, so
`send_and_log_listener.py` must not poll while the gateway runs.
Standalone polling is for isolated tests only (one `getUpdates` client
per bot, a second one 409s).

`message_reaction` must be in the bot's `allowed_updates`.

On an event:

1. Look up `contacts` where `telegram_message_id = message_id`.
2. No row → ignore (already processed, or not ours).
3. Row `new` + 👍 → `log_contact(email, company_name, domain,
   source, notes, draft_subject, draft_body, message_id)`.
4. Row `new` + 👎 → patch `status = 'skipped'`, clear draft fields.
5. Row `contacted` + 👍 → same `log_contact` call, no notes.
6. Row `contacted` + 👎 → patch `status = 'closed'`, clear draft fields.
7. Any other status or reaction → ignore. Hard stops can't be reached
   here because `log_contact` refuses to overwrite them anyway.

## What this gives you

`messages` holds every touch verbatim with its step, so
`first_touches_today()` is a real count and `/status` can report
sends, skip rate, and draft-to-decision lag. A rising skip rate is the
earliest sign that research is drifting, long before reply rate says
anything.

## What this stage does not do

No drafting, no research, no verification, no sending.

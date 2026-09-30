# send-and-log.md: Reaction to Database Write

Closes the loop. A draft sits on Telegram until Adam reacts. The
reaction is the only signal; nothing runs on a timer.

## The two reactions on a draft

| Reaction | On a first touch (`status = 'new'`) | On a follow-up email (`status = 'contacted'`) |
|---|---|---|
| 👍 | `log_contact` → `contacted`, touch 1 logged | `log_contact` → count +1, touch logged, next due set |
| 👎 | `status = 'skipped'` | `status = 'closed'` |

## The three reactions on a task

Look up `messages` by `telegram_message_id` and `outcome = 'pending'`
first. If a row exists, call `resolve_touch` and stop. Do not fall
through to the draft path. `log_contact` is not used for tasks. It
still refuses to overwrite a hard stop if a draft reaction reaches it.

| Reaction | Outcome | Effect |
|---|---|---|
| 👍 | `done` | Logged. Letter: call due in 4 days. Call: sequence ends, `closed`. LinkedIn: the message row is the whole record. |
| 👎 | `skipped` | This task only. Letter: call due now. Call: sequence ends, `closed`. |
| 🤝 | `responded` | `status = 'replied'`. Wins if another emoji is also present. |

If `resolve_touch` returns null, the task was already resolved. Ignore it.

Both clear `draft_subject`, `draft_body`, `telegram_message_id` on the
contact. That is the idempotency guard: a second reaction on the same
message finds no matching row and is ignored.

## Mechanics

Production path is the Hermes plugin `send-and-log`. Email-bot
reactions arrive on `gateway_platform_event` with `scope=main`. The
gateway already long-polls that bot, so `send_and_log_listener.py`
must not poll it while the gateway runs.

LinkedIn reactions are a second poller inside the same plugin, using
`TELEGRAM_LI_BOT_TOKEN` only, `scope=linkedin`. That token is a
different bot, so it does not 409 the gateway. A LinkedIn reaction
never falls through to an email draft, even if the message ids match.
If a pending email task and a pending LinkedIn task share a message
id, neither reaction is applied.

`message_reaction` must be in the bot's `allowed_updates`.

On an event:

1. Look up `messages` where `telegram_message_id = message_id` and
   `outcome = 'pending'`.
2. Row found → `resolve_touch(message_id, done|skipped|responded)` for
   👍 / 👎 / 🤝. Stop.
3. No pending task → look up `contacts` where
   `telegram_message_id = message_id`.
4. No row → ignore (already processed, or not ours).
5. Row `new` + 👍 → `log_contact(email, company_name, domain,
   source, notes, draft_subject, draft_body, message_id)`.
6. Row `new` + 👎 → patch `status = 'skipped'`, clear draft fields.
7. Row `contacted` + 👍 → same `log_contact` call, no notes.
8. Row `contacted` + 👎 → patch `status = 'closed'`, clear draft fields.
9. Any other status or reaction → ignore. Hard stops can't be reached
   here because `log_contact` refuses to overwrite them anyway.

## What this gives you

`messages` holds every touch verbatim with its step, so
`first_touches_today()` is a real count and `/status` can report
sends, skip rate, and draft-to-decision lag. A rising skip rate is the
earliest sign that research is drifting, long before reply rate says
anything.

## What this stage does not do

No drafting, no research, no verification, no sending.

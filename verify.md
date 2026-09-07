# verify.md — Email Verification

Runs on every candidate that has cleared `research.md`, immediately before
`draft.md`. Universal, not conditional: applies equally to a published
address scraped from a company's own site and to one constructed from a
name pattern in `research.md`. A stale published address bounces exactly
the same way a bad guess does, and at this volume the cost of checking
both is close to nothing.

## Why MillionVerifier

Plain single GET-request API, key and email as parameters, no bulk upload
machinery needed. Roughly $0.0004 per check, so the day's full 10 costs a
fraction of a penny. Free trial credits exist and likely cover this
indefinitely at this volume. Chosen over NeverBounce specifically:
independent testing found NeverBounce carrying a materially higher false
positive rate, which is the one failure mode that actually damages
domain reputation, confidently marking a bad address as good, so it's a
worse fit for the actual goal here despite otherwise being competent.

## Call

```
GET https://api.millionverifier.com/api/v3/?api={MILLIONVERIFIER_API_KEY}&email={candidate_email}&timeout=10
```

`timeout` is optional, 2 to 60 seconds, defaults to 20. 10 is plenty at
this volume and keeps a single hung check from stalling the run.

Key lives in Hermes' `.env` on the Vultr box, same as the others. Never
in chat, never in the repo.

## Response shape

```json
{
  "email": "candidate@company.com",
  "quality": "good",
  "result": "invalid",
  "resultcode": 6,
  "subresult": "bad_domain",
  "free": false,
  "role": false,
  "didyoumean": "",
  "credits": 471,
  "executiontime": 2,
  "error": ""
}
```

`result` is what Stage decisions below are keyed on. `error` is a
separate, API-level failure channel, not an email-quality result — see
below. `didyoumean` is a suggested correction when MillionVerifier
thinks the domain is a typo (e.g. `gmal.com` → `gmail.com`); log it,
don't auto-apply it. A typo correction changes who the email is actually
sent to, that's a judgement call for `research.md`'s next run, not
something this stage silently fixes.

## API-level errors, distinct from email results

If `error` is non-empty, the check itself failed, this is not a
statement about the email's deliverability. Known values: no email
given, missing or invalid API key, insufficient credits, IP blocked,
internal error. Treat exactly like `unknown`, hold back and allow a
retry on a later run, never treat an errored check as equivalent to
`invalid`.

## Credits

```
GET https://api.millionverifier.com/api/v3/credits?api={MILLIONVERIFIER_API_KEY}
```

Returns `credits`, `bulk_credits`, `renewing_credits`, `plan`. No
automated alerting built for this, check by hand occasionally, or let an
`INSUFFICIENT_CREDITS` error (handled above as a hold-back-and-retry
case) be the signal that it's time to look.

## Result mapping

| Result | Meaning | Action |
|---|---|---|
| `ok` | Mailbox confirmed to exist | Proceed to `draft.md` |
| `catch_all` | Domain accepts everything, individual mailbox unconfirmable | Hold back — do not draft or send |
| `unknown` | Timeout or inconclusive (often temporary, e.g. greylisting) | Hold back for this run, safe to retry a later run rather than a permanent reject |
| `invalid` | Confirmed non-existent | Drop candidate entirely |
| `disposable` | Throwaway address | Drop candidate entirely |

`free` and `role` come back as flags alongside the above, not separate
results — informational only, never blocking on their own. A `role`
result (info@, sales@) usually means `research.md`'s Stage 1 fell back
to a role-addressed opener rather than finding a named buyer, which is
already accounted for there, not a new problem to solve here.

## What "hold back" means in practice

Not a permanent rejection. Update `contacts.email_verification_status`
to the result and leave `status` as `new`. This candidate simply doesn't
fill today's quota — `find.md`'s next run backfills the gap from fresh
candidates rather than this one being force-sent regardless. A
`catch_all` result today doesn't mean the company's a dead end forever,
just that this address isn't confirmable right now.

## Write-back

`contacts.email_verification_status` gets set on every check: `ok`,
`catch_all`, `unknown`, `invalid`, or `disposable`. This is a real
column, not buried in `notes`, specifically so it's queryable later —
e.g. checking how often `research.md`'s constructed guesses actually
turn out valid, which is the kind of thing worth knowing before ever
loosening this gate.

## What this stage does not do

No drafting, no research, no send. A candidate either comes out of this
stage with a confirmed deliverable address or it doesn't reach
`draft.md` at all.

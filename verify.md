# verify.md: Email Verification

Runs inside `deliver.py send`, on every candidate, immediately before
the contact is inserted. Universal: a published address bounces the
same way a bad guess does. `scripts/verify.py`, reusable on its own.

## MillionVerifier

Single GET, key and email as parameters, about $0.0004 a check.

```
GET https://api.millionverifier.com/api/v3/?api={KEY}&email={email}&timeout=10
```

`result` drives the decision. `error` is an API-level failure, not a
statement about the email. `didyoumean` is logged, never auto-applied.

## Result mapping

| Result | Decision | `companies_seen.outcome` |
|---|---|---|
| `ok` | Proceed, insert contact | `promoted_to_contacts` |
| `catch_all` | Hold, don't draft | `held_verify` |
| `unknown` | Hold, retry a later run | `held_verify` |
| API error | Hold, retry a later run | `held_verify` |
| `invalid` | Drop this address | `rejected_verify` |
| `disposable` | Drop this address | `rejected_verify` |

`free` and `role` are flags, informational only. A `role` result
means a generic inbox, already handled by role-addressing in
`research.md`.

Held or dropped candidates don't fill today's quota; `/next` moves to
the next pending row. A `rejected_verify` is about the address, not
the company: research can come back with a different address on a
later run, which is why the reason records the address that failed.

## Write-back

On a successful insert, `contacts.email_verification_status = 'ok'`.
Held and dropped candidates never reach `contacts`, the result lives
in `companies_seen.reason`.

## Credits

`GET https://api.millionverifier.com/api/v3/credits?api={KEY}`. No
alerting. An insufficient-credits error is handled as a hold and is
the signal to top up.

# check.md: Contact History Check

Runs against `contacts` before any research or drafting. Same lookup
whether `next.py` is clearing a campaign queue or Adam runs `/check`
on a one-off email. `scripts/check.py`, no AI.

```sql
select status, unsubscribed_at, last_contacted_at, contact_count, notes, domain
from contacts where email = :candidate_email;
```

Dedup key is `email`, not `domain`. A second person at the same
company under a different address is not blocked.

## Decision table

| Result | Decision |
|---|---|
| No row | Clear. First touch. |
| `status = 'new'` | Clear, a draft already exists, don't make another. |
| `unsubscribed` | Hard stop. No draft, no log, no exception. |
| `do_not_contact` | Hard stop. Only ever set by hand. |
| `replied` | Hard stop. Ownership moved to the Zoho inbox. |
| `contacted` | Flag. A sequence is live, `followup.md` owns it. Don't start a second first touch. |
| `skipped`, `closed` | Flag. Surface the history; a fresh first touch is a judgement call, not a default. |

Hard stop means the candidate's `companies_seen` row gets
`outcome = 'rejected_check'` with the status as reason, and the
pipeline moves on.

## Repeat contact heuristic

For `skipped` or `closed`: under ~21 days since `last_contacted_at`
is probably too soon, beyond that read `notes` and `angle` so a new
opener doesn't repeat the old one. Starting point, not a rule.

## Domain-level history

Informational only. The script reports how many other contacts exist
at the domain and how many are unsubscribed, so a draft can avoid
looking like a company-wide blast. It never changes the decision.

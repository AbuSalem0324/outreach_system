# check.md — Contact History Check

Runs against the `contacts` table before any research or drafting happens.
Same lookup, same decision rule, whether it's Hermes clearing its daily
`find.md` queue or a manual, one-off company Adam brings up outside the
pipeline entirely. One rule, two entry points.

```sql
select status, unsubscribed_at, last_contacted_at, contact_count, notes, domain
from contacts
where email = :candidate_email;
```

Dedup key is `email`, not `domain` — a second contact at the same company
under a different address is not blocked by this check. See the note at the
end for the one place domain history still shows up, informationally only.

## Decision table

| Result | Action |
|---|---|
| No row found | Clear. First touch. Proceed to `research.md`. |
| `status = 'new'` | Clear. This is `find.md`'s own queue — proceed. |
| `status = 'unsubscribed'` | **Hard stop.** No draft, no log attempt, no exception. This is the one rule nothing overrides. |
| `status = 'do_not_contact'` | **Hard stop.** Manually set — see below. |
| `status = 'replied'` | **Hard stop for this pipeline.** Once a contact has replied, ownership moves to the Zoho inbox and manual follow-up. This system does not re-enter someone into automated outreach after a reply, regardless of how long it's been. |
| `status = 'contacted'`, no reply yet | **Not auto-blocked, not auto-allowed.** Flag for judgement — see below. |

## Hard stops: what "stop" means

No draft gets written. No entry gets logged. No email gets sent. The
pipeline simply moves to the next candidate. This is not a soft
preference — `unsubscribed` and `do_not_contact` are compliance and
relationship boundaries respectively, and nothing downstream should be
able to override them by re-discovering the same person through a
different route (e.g. `find.md` surfacing them again from a fresh Places
query, which `find.md`'s own Stage 6 dedup should already prevent, but
this is the backstop if it doesn't).

`do_not_contact` only ever gets set manually — this system has no way to
read replies (they land in Zoho, outside this pipeline's visibility), so
if a reply is hostile, a legal complaint, or a hard bounce, that's Adam
setting the flag by hand, not something inferred automatically.

## Repeat contact: flagged, not blocked

When `status = 'contacted'` with no reply, surface the history rather
than deciding for the user:

- `last_contacted_at` — how long ago
- `contact_count` — how many times
- `notes` — what the prior angle(s) were, so a follow-up doesn't repeat
  the same opener

Starting heuristic, not a hard rule: treat anything under ~21 days as
"probably too soon, ask before proceeding," and anything beyond that as
a judgement call informed by the notes rather than a default block.
This threshold is a starting point to sanity-check against, not
something to enforce silently — the actual call belongs to whoever's
drafting.

## Domain-level history — informational only, never blocking

Adam has explicitly ruled out domain-based blocking: a second contact at
a company where someone else was already reached is not treated as a
repeat. The only domain-level behaviour this check performs is optional
and soft — surfacing "N other contacts at this domain, one of them is
`unsubscribed`" as a caution alongside the result, purely so a draft can
account for it if relevant (e.g. avoiding a company-wide send pattern
that reads as spam internally). It never changes the decision table
above on its own.

# schema.md: Deployed Supabase Schema

Project **CRM** `pmbzagybwcwhcmlrkrbu`, schema `public`, RLS enabled
on every table, secret-key access only. Checked against the live
database on 2026-09-12. If this file and the database disagree, the
database wins and this file gets fixed.

## `campaigns`

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| name | text | caption or filename |
| icp_id | text | |
| file_name | text | |
| file_sha256 | text unique | same file twice is refused |
| row_count | int | |
| created_at | timestamptz | |

## `companies_seen`

Every company that has been through the pipeline, keyed on
`company_number` (unique where not null).

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| company_number | text | uppercase, digits zero-padded to 8 |
| company_name | text | from Endole |
| website | text | |
| email | text | from Endole if exported |
| sic_code | text | primary |
| domain | text | |
| icp_id | text | |
| campaign_id | uuid fk campaigns | |
| csv_order | int | file order, `/next` walks it |
| raw | jsonb | the whole Endole row |
| outcome | text | see below |
| reason | text | why |
| first_seen_at, last_checked_at | timestamptz | |
| place_id | text | legacy, unused |

`outcome` values: `pending`, `in_research`, `awaiting_pick`,
`promoted_to_contacts`, `rejected_ingest`, `rejected_research`,
`rejected_check`, `rejected_verify`, `held_verify`, `held_review`
(research parked it with a question for Adam, in `reason`),
`seen_before`.
Older rows carry
Places-era values (`passed_to_ai`, `rejected_score` and so on); the
new pipeline never selects them.

## `contacts`

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| email | text unique | the dedup key |
| company_name, domain, company_number, sic_code | text | |
| campaign_id | uuid fk | |
| icp_id | text | |
| source | text | `endole_campaign` |
| status | text | `new`, `contacted`, `skipped`, `closed`, `replied`, `do_not_contact`, `unsubscribed` |
| buyer_name, buyer_role | text | from research |
| angle | text | the one sentence follow-ups reuse |
| notes | text | research summary, appended over time |
| draft_subject, draft_body | text | pending draft, cleared on reaction |
| telegram_message_id | bigint | current draft's message, cleared on reaction |
| draft_delivered_at | timestamptz | |
| email_verification_status | text | `not_checked`, `ok`, ... |
| first_contacted_at, last_contacted_at | timestamptz | |
| contact_count | int | doubles as sequence step |
| next_due_at | timestamptz | trigger-maintained, except `resolve_touch` after a letter decision |
| unsubscribed_at | timestamptz | |
| linkedin_url | text | chosen person only |
| phone | text | chosen person only |
| phone_type | text | `direct` named work line; `mobile` may be personal, TPS before calling; `switchboard` company main line |
| postal_address | text | trading address from the company's own site. Never the Companies House registered office. |
| enrichment_source | text | where linkedin_url / phone came from, e.g. `hunter`. Not set for postal address alone. |
| enriched_at | timestamptz | set when linkedin_url or phone is stored |
| created_at, updated_at | timestamptz | |

## `messages`

One row per touch actually sent.

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| contact_id | uuid fk contacts | |
| direction | text | `outbound` / `inbound` |
| channel | text | `email` / `linkedin` / `phone` / `letter` / `other`. Default `email`. |
| sequence_step | int | 1, 2, 3, 4 |
| outcome | text | `pending` / `done` / `skipped` / `responded`. Default `done`. Email rows from `log_contact` stay `done`. Task rows start `pending`. |
| subject, body | text | verbatim |
| variant | text | unused for now |
| telegram_message_id | bigint | the draft that was approved |
| sent_at, created_at | timestamptz | |

## Functions and triggers

- `log_contact(p_email, p_company_name, p_domain, p_source, p_notes,
  p_subject, p_body, p_telegram_message_id) returns contacts`.
  Upserts on email, sets `contacted`, bumps `contact_count`, appends
  notes, clears the pending draft, inserts a `messages` row when
  subject or body is given. Refuses to change `unsubscribed`,
  `do_not_contact`, `replied`.
- `first_touches_today() returns int`. Count of `sequence_step = 1`
  messages sent since midnight Europe/London.
- `contacts_set_next_due()` trigger, before insert or update on
  `contacts`. +3 days after touch 1, +7 after touch 2, +7 after touch
  3, null after that or on any terminal status. It does not recompute
  `next_due_at` when only a letter decision moves that column.
- `resolve_touch(p_telegram_message_id bigint, p_outcome text) returns messages`.
  Acts only on a row still `pending`. 👍/👎/🤝 map to `done` /
  `skipped` / `responded`. Letter `done` sets the call due in 4 days;
  letter `skipped` sets it due now. Phone either way closes the
  sequence. LinkedIn writes the message row only. `responded` sets
  `status = 'replied'`. Execute is granted to `service_role` only.
- `set_contacts_updated_at()` trigger.
- `rls_auto_enable()` event trigger, enables RLS on any new public
  table.

`messages` is one row per touch sent or decided, not only sent.
Pending task rows exist before Adam acts.

The enrichment columns and `resolve_touch` are defined by
`20260928_multichannel_sequence.sql`. Confirm this file against the
live OpenAPI after that migration is applied. If they disagree, the
database wins.

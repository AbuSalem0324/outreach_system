# ingest.md: Endole CSV In

One Endole export, one campaign. Runs when a CSV lands in the Telegram
chat. Deterministic, no AI, `scripts/ingest.py`.

## What Endole gives us

Endole exports whichever fields Adam picked in the Export Explorer, so
column names are not stable between campaigns. Expect some subset of:
company name, company number, status, SIC code and description,
website, email, telephone, employees, turnover, total assets, company
size, age or incorporation date, director names and roles, address
lines, town, region, postcode. The script maps headers by fuzzy match
to a fixed internal set and keeps every column, mapped or not, in
`companies_seen.raw` as JSON so `research.md` can read the lot.

Internal fields the mapper tries to find: `company_number`,
`company_name`, `website`, `email`, `sic_code`, `employees`,
`turnover`, `region`, `postcode`, `directors`. Missing ones are simply
null; the row still ingests.

`company_number` is the anchor. Normalised to uppercase, digits-only
numbers zero-padded to eight characters, so `445790` and `00445790`
are the same company. A row with no company number is ingested with
`outcome = 'rejected_ingest'`, `reason = 'no_company_number'`, because
nothing downstream can join on it.

## What the script does

1. Hash the file. A hash already in `campaigns.file_sha256` means the
   same export twice; refuse, report the existing campaign id.
2. Insert the `campaigns` row: name (caption or filename), `icp_id`,
   filename, hash, row count.
3. For each row, in file order (`csv_order` preserved):
   - Company number already in `companies_seen` with any outcome other
     than `pending` → insert nothing, count it as `seen_before`. It was
     evaluated under an earlier campaign and the outcome and reason
     are still there to read.
   - Otherwise insert with `outcome = 'pending'`, the mapped fields,
     `campaign_id`, and `raw`.
4. Print a JSON summary: campaign id, rows, new, seen before, without
   website, without email, without company number.

## What it does not do

No `contacts` writes. No research. No enrichment calls. The CSV is the
input; `/next` decides who gets looked at and in what order.

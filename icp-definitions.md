# icp-definitions.md: Who We Actually Want

Endole does the hard filtering before a CSV ever reaches this system:
sector, region, size band, status. So the ICP here is not a filter
recipe, it is a description of character. Within a batch of companies
that all look alike on paper, which ones plausibly have the problem
DataBard solves and the autonomy to buy a fix for it, and which ones
should be dropped in research despite matching every column.

Every `contacts` row is tagged with the `icp_id` that sourced it, via
the campaign, so reply rate is groupable per ICP.

---

## ICP A: "Home Turf" (credibility-led)

```yaml
icp_id: home-turf-fmcg-v1
active: true
name: Food & Drink Manufacturing / FMCG Wholesale / Logistics
endole_filter_expectations:
  # What the CSV is expected to have been filtered on. Research does
  # not re-check these, it trusts the export.
  regions: [Yorkshire, North East England, North West England]
  status: active
  exclude_accounts: [micro-entity, dormant]
  sic_families: ["10.*", "11.07", "46.3*", "46.17", "49.41", "52.10", "52.21", "52.29"]
character:
  # What research is looking for on the site and in search, beyond the
  # columns. None of these is required; together they say "buyer".
  - Runs a physical operation: production line, cold store, fleet,
    multiple sites, shift patterns
  - Sells to trade (wholesalers, retailers, caterers), so has demand
    and stock planning to do
  - Independent, owner-managed or a small board, decisions made in the
    building
  - No visible sign of a modern data stack (no BI embeds, no ERP
    vendor case study about them, no data or analytics roles advertised)
  - Employee band roughly 20 to 250 where Endole gives it
disqualifiers:
  # Any one of these is a rejected_research with the reason recorded.
  - Subsidiary or recently acquired: group structure or a search
    result shows a parent that would own the tooling decision
  - In administration, liquidation, strike-off, or a search shows
    closure or a fire sale
  - A consultancy, agency, broker, or software vendor, whatever the
    SIC says
  - Already tooled: visible Power BI / Tableau / Looker / Qlik
    embeds, or a vendor case study naming them as a customer
  - A shell, holding company, or property vehicle with no operation
  - Site is dead, parked, or clearly abandoned
buyer_titles:
  - Operations Director
  - Supply Chain Manager
  - Head of Operations
  - Managing Director
  - Finance Director
pitch_angle: >
  Leads with direct operator credibility: years at Tesco from team
  leader to store manager, plus IT service desk inside 2 Sisters Food
  Group. The pitch is "I've run this kind of operation," not a generic
  data-consultant approach.
```

---

## ICP B: "Generalist Control"

```yaml
icp_id: generalist-control-v1
active: false  # holds until ICP A has a real reply-rate baseline
name: Light Engineering / Professional Services
endole_filter_expectations:
  regions: [England]
  status: active
  exclude_accounts: [micro-entity, dormant]
  sic_families: ["25.11", "25.62", "28.29", "69.20"]
character:
  - Same shape as ICP A minus the food specifics: physical or
    process-heavy operation, trade customers, independent, no visible
    data stack
disqualifiers:
  - Same list as ICP A, and 70.22 management consultancies are out
    entirely
buyer_titles:
  - Operations Director
  - Managing Director
  - Finance Director
pitch_angle: >
  Same offer and structure as ICP A without the Tesco / 2 Sisters hook.
  Generic SME data framing. Exists only to test whether the credibility
  hook is what drives replies.
```

---

## What the A/B test measures

One variable in what gets read: sector-specific operator credibility
versus generic framing. Do not activate ICP B until ICP A has enough
sends for a comparison to mean anything.

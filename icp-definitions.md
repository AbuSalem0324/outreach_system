# ICP Definitions — DataBard Outreach

Each ICP is a standalone, versioned target definition. The find/check/research/draft
pipeline reads whichever ICP is `active`; nothing pipeline-side is hardcoded to a
sector. Every row landed in `contacts` is tagged with the `icp_id` that sourced it,
so reply rate becomes a groupable metric per ICP, not something reconstructed later.

---

## ICP A — "Home Turf" (credibility-led)

```yaml
icp_id: home-turf-fmcg-v1
active: true
name: Food & Drink Manufacturing / FMCG Wholesale / Logistics
geography:
  primary: [Yorkshire, North East England, North West England]
  secondary: [rest of England]  # only once ICP A has enough volume to expand
company_size_band:
  companies_house_accounts_type: [small, medium]
  # small: turnover ≤£15m, balance sheet ≤£7.5m, ≤50 employees
  # medium: turnover ≤£54m, balance sheet ≤£27m, ≤250 employees
  # (Companies Act thresholds effective 6 April 2025)
sic_codes:
  food_drink_manufacturing:
    - "10.11"  # Processing and preserving of meat
    - "10.12"  # Processing and preserving of poultry meat
    - "10.13"  # Production of meat and poultry meat products
    - "10.20"  # Processing and preserving of fish, crustaceans, molluscs
    - "10.31"  # Processing and preserving of potatoes
    - "10.39"  # Other processing and preserving of fruit and vegetables
    - "10.51"  # Operation of dairies and cheese making
    - "10.61"  # Manufacture of grain mill products
    - "10.71"  # Manufacture of bread, fresh pastry goods and cakes
    - "10.72"  # Manufacture of rusks and biscuits; preserved pastry/cakes
    - "10.85"  # Manufacture of prepared meals and dishes
    - "10.89"  # Manufacture of other food products n.e.c.
    - "10.91"  # Manufacture of prepared feeds for farm animals
    - "10.92"  # Manufacture of prepared pet foods
    - "11.07"  # Manufacture of soft drinks; bottled waters
  fmcg_wholesale_distribution:
    - "46.17"  # Agents in food, beverages, tobacco
    - "46.31"  # Wholesale of fruit and vegetables
    - "46.32"  # Wholesale of meat and meat products
    - "46.33"  # Wholesale of dairy products, eggs, edible oils and fats
    - "46.34"  # Wholesale of beverages
    - "46.36"  # Wholesale of sugar, chocolate, sugar confectionery
    - "46.37"  # Wholesale of coffee, tea, cocoa, spices
    - "46.38"  # Wholesale of other food (incl. fish, crustaceans, molluscs)
    - "46.39"  # Non-specialised wholesale of food, beverages, tobacco
  logistics:
    - "49.41"  # Freight transport by road
    - "52.10"  # Warehousing and storage
    - "52.21"  # Service activities incidental to land transport
    - "52.29"  # Other transportation support activities (freight forwarding)
buyer_titles:
  - Operations Director
  - Supply Chain Manager
  - Head of Operations
  - Managing Director  # SME band — often the actual tooling decision-maker
  - Finance Director
pitch_angle: >
  Leads with direct operator credibility: 6 years at Tesco (team leader to
  store manager) plus IT service desk experience inside 2 Sisters Food Group,
  an actual FMCG manufacturer. The pitch is "I've run this kind of operation,"
  not a generic data-consultant approach.
exclusions:
  - Boutique consultancies (never converts — buyer-direct only from here on)
  - Micro-entity accounts filers (too small to be a credible buyer)
```

---

## ICP B — "Generalist Control"

```yaml
icp_id: generalist-control-v1
active: false  # holds until ICP A has enough sends to be worth comparing against
name: Light Engineering / Professional Services (no sector-specific credibility)
geography:
  primary: [England, national]
company_size_band:
  companies_house_accounts_type: [small, medium]
sic_codes:
  light_engineering:
    - "25.11"  # Manufacture of metal structures and parts
    - "25.62"  # Machining
    - "28.29"  # Manufacture of other general-purpose machinery n.e.c.
  professional_services:
    - "70.22"  # Business and other management consultancy activities
    - "69.20"  # Accounting, bookkeeping, auditing activities
buyer_titles:
  - Operations Director
  - Managing Director
  - Finance Director
pitch_angle: >
  Same message structure and offer as ICP A, but WITHOUT the Tesco/2 Sisters
  credibility hook — generic "SME data science" framing instead. The point of
  this ICP is not the sector itself; it's a controlled comparison to isolate
  whether the operator-credibility narrative is what's actually driving
  replies, or whether the offer converts on its own regardless of sector fit.
exclusions:
  - Boutique consultancies
  - Micro-entity accounts filers
```

---

## What the A/B test actually measures

Only one variable is meant to differ in what gets *read*: whether the opener
carries specific, verifiable operator credibility for the recipient's sector,
or a generic SME-data-science framing. Company size band, buyer titles, offer
structure, and pricing stay identical across both, so a reply-rate gap can be
attributed to the credibility hook rather than to some other confound.

Do not activate ICP B until ICP A has run long enough to have a real reply-rate
baseline — a comparison against thin data isn't a comparison.

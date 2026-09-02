# Regulatory factors

*Generated from `factors/regulatory.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `reg.permitting_timeline` Permitting timeline | months | C | 8 | 7 | 7 |  |
| `reg.environmental_review` Environmental review burden | category | B | 7 | 5 | 6 |  |
| `reg.tax_incentives` Tax incentive package | index_0_100 | B | 7 | 5 | 6 |  |
| `reg.air_permit` Generator air permitting | category | B | 6 | 4 | 5 |  |
| `reg.data_sovereignty` Data sovereignty and cross-border regime | category | C | 5 | 6 | 6 |  |
| `reg.export_controls` Accelerator export control exposure | category | B | 9 | 6 | 6 | gate.compute_legally_deployable |
| `reg.jurisdiction_stability` Jurisdictional and political stability | index_0_100 | B | 6 | 5 | 6 |  |

## Permitting timeline

`reg.permitting_timeline` · **months** · lower_is_better · best obtainable tier **C**

> Historical median months from application to construction permit for comparable projects.

**Normalization curve** (value → score):

| 0 | 3 | 6 | 12 | 18 | 30 | 48 | 72 |
|---|---|---|---|---|---|---|---|
| 100 | 94 | 86 | 68 | 48 | 22 | 4 | 0 |

**Sources:** `county_permit_records`, `state_env_agency`, `moef_india`, `mee_china`, `local_news`

Derive from actual comparable projects in the same jurisdiction wherever possible — jurisdictions vary far more than national averages suggest, and the variance within a US state between two adjacent counties can exceed the variance between countries. Where no comparable exists, use the jurisdiction's statutory timeline and add the observed national slip factor, marking it Tier D.

## Environmental review burden

`reg.environmental_review` · **category** · categorical · best obtainable tier **B**

> What level of environmental assessment is triggered?

**Categories:**

- `categorical_exclusion` → 100
- `screening_only` → 82
- `full_ea_eia` → 52
- `full_eis_with_litigation_risk` → 22
- `prohibited` → 0
- `unknown` → —

**Sources:** `nepa_ceq`, `state_env_agency`, `eia_notification_india`, `mee_china`, `eu_eia_directive`

Federal nexus is the key US question — a purely private project on private land with no federal permit, funding, or land generally avoids NEPA entirely, while a wetland fill permit or federal land crossing pulls the whole project in. In India, whether the project falls under the EIA Notification 2006 schedule depends on built-up area and category; most standalone data centers fall outside it, but associated captive power generation frequently does not.

## Tax incentive package

`reg.tax_incentives` · **index_0_100** · higher_is_better · best obtainable tier **B**

> What is the net present value of available incentives?

**Normalization curve** (value → score):

| 0 | 15 | 35 | 55 | 75 | 100 |
|---|---|---|---|---|---|
| 0 | 22 | 45 | 65 | 85 | 100 |

**Sources:** `state_statute`, `state_edc`, `state_dc_policy_india`, `provincial_policy_cn`

Sales tax exemption on IT equipment dominates everything else for an AI campus, because the equipment is the overwhelming majority of project cost — at $10 B of GPUs, a 6% sales tax exemption is worth $600 M, which is larger than the entire land and construction budget of most sites. Always cite the statute, verify the current sunset date, and check the qualification thresholds (minimum investment, minimum jobs) which many AI campuses fail on the jobs test. Several US states tightened or paused data center incentives in 2024-2026; verify currency.

## Generator air permitting

`reg.air_permit` · **category** · categorical · best obtainable tier **B**

> Can the required backup generation be permitted?

**Categories:**

- `minor_source_routine` → 100
- `minor_source_constrained` → 74
- `major_source_psd_required` → 42
- `nonattainment_offsets_required` → 20
- `effectively_blocked` → 0
- `unknown` → —

**Sources:** `epa_nonattainment`, `state_air_agency`, `cpcb_india`, `mee_china`

A 500 MW campus needs roughly 150-250 MW-equivalent of diesel or gas backup, which is a large emissions source even at low run hours. Non-attainment areas require emission offsets that may be unavailable at any price. This has become a live constraint in several US metros and is a common late-stage surprise. Where on-site prime power generation is contemplated rather than backup only, the permit becomes a major-source review and the timeline changes categorically.

## Data sovereignty and cross-border regime

`reg.data_sovereignty` · **category** · categorical · best obtainable tier **C**

> Do local law and cross-border data rules match the intended workload?

**Categories:**

- `open_and_stable` → 100
- `open_with_sectoral_rules` → 78
- `localization_required` → 50
- `restrictive_with_access_mandates` → 25
- `incompatible` → 0
- `unknown` → —

**Sources:** `national_data_law`, `gdpr_adequacy`, `dpdp_india`, `cac_china`, `itif_data_localization`

Localization requirements are an opportunity as often as a constraint — they are precisely why in-country capacity gets built. Score against the intended workload and customer base, not in the abstract. Government access mandates matter enormously to some tenants and not at all to others; record the fact and let the profile weight it.

## Accelerator export control exposure

`reg.export_controls` · **category** · categorical · best obtainable tier **B**

> Can the intended compute legally be installed and operated here?

**Categories:**

- `unrestricted` → 100
- `license_routine` → 72
- `license_uncertain` → 38
- `restricted_high_end` → 15
- `prohibited` → 0
- `unknown` → —

**Sources:** `bis_entity_list`, `us_ear_ai_rules`, `eu_dual_use`, `national_import_rules`

This factor is what distinguishes an "AI data center" analysis from a generic data center analysis, and it is the reason a technically excellent site in certain jurisdictions is not investable for frontier training. US export controls on advanced accelerators have changed repeatedly since 2022 and are the single fastest-moving input in this framework — always check the current rule text and record the rule version and date in the evidence ledger, because an analysis citing a superseded rule is worse than no analysis. For China in particular, distinguish clearly between domestic-accelerator deployments and those requiring controlled Western hardware; they are different investments.

## Jurisdictional and political stability

`reg.jurisdiction_stability` · **index_0_100** · higher_is_better · best obtainable tier **B**

> How stable are the rules over a 25-year asset life?

**Normalization curve** (value → score):

| 0 | 20 | 40 | 60 | 80 | 100 |
|---|---|---|---|---|---|
| 0 | 18 | 40 | 62 | 85 | 100 |

**Sources:** `world_bank_wgi`, `oecd_country_risk`, `eiu_democracy_index`

Composite of rule of law, regulatory quality, contract enforcement, currency convertibility, and expropriation risk. Applied at national level and adjusted for subnational variation where it is material. A low score here should widen the required return rather than eliminate the site — but it must be visible, because it is routinely omitted from technical site assessments.

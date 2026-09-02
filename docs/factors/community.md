# Community factors

*Generated from `factors/community.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `com.opposition_risk` Organized opposition risk | category | C | 8 | 6 | 6 | gate.no_active_moratorium |
| `com.residential_proximity` Residential proximity and noise exposure | dwellings_within_1km | A | 7 | 4 | 5 |  |
| `com.economic_alignment` Local economic alignment | index_0_100 | C | 5 | 4 | 4 |  |
| `com.grid_cost_allocation` Ratepayer cost allocation sensitivity | category | C | 6 | 3 | 4 |  |

## Organized opposition risk

`com.opposition_risk` · **category** · categorical · best obtainable tier **C**

> Is there active, organized opposition to data centers in this jurisdiction?

**Categories:**

- `supportive_precedent` → 100
- `neutral_no_precedent` → 72
- `mixed_contested` → 45
- `organized_opposition` → 20
- `moratorium_active` → 0
- `unknown` → —

**Sources:** `local_news_search`, `county_meeting_minutes`, `change_org`, `dc_watch_trackers`

Search the county or municipality name with "data center" plus terms like moratorium, rezoning, opposition, hearing, and referendum, across at least the trailing 24 months. Read the actual meeting minutes where available — the vote counts on prior applications are the single best predictor of the next one. An active moratorium is a hard gate. Note that opposition frequently clusters: one contested project in a county reliably raises the temperature for the next.

## Residential proximity and noise exposure

`com.residential_proximity` · **dwellings_within_1km** · lower_is_better · best obtainable tier **A**

> How many residences fall within the noise-relevant buffer?

**Normalization curve** (value → score):

| 0 | 10 | 50 | 200 | 600 | 1500 | 4000 |
|---|---|---|---|---|---|---|
| 100 | 92 | 78 | 55 | 30 | 10 | 0 |

**Sources:** `ghsl_built_s`, `osm_buildings`, `worldpop`, `microsoft_building_footprints`

Noise from chillers, dry coolers, and generator testing is the most common specific complaint in US data center opposition — more common than water, and far more common than power. Distance is the cheapest possible mitigation, which makes this factor unusually actionable. Where dwelling counts are high, the Recommender should price acoustic barriers, low-noise fan selections, and setback increases explicitly.

## Local economic alignment

`com.economic_alignment` · **index_0_100** · higher_is_better · best obtainable tier **C**

> Does the local economy want this kind of investment?

**Normalization curve** (value → score):

| 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|
| 0 | 25 | 50 | 75 | 100 |

**Sources:** `bls_local_unemployment`, `county_edc_priorities`, `census_acs`, `state_edc`

Composite of unemployment, tax base concentration, EDC stated priorities, and whether the county has actively recruited data centers. Counties with a narrow tax base and an active EDC are structurally the most welcoming. Be candid in the report that AI data centers create very few permanent jobs relative to their capital cost — typically 25-60 permanent roles for a large campus — because overstating jobs is the fastest way to lose community trust, and because the permanent-jobs number is what local opposition will fact-check first.

## Ratepayer cost allocation sensitivity

`com.grid_cost_allocation` · **category** · categorical · best obtainable tier **C**

> Will this load raise local retail rates, and is that politically live?

**Categories:**

- `isolated_or_self_supplied` → 100
- `cost_causation_rules_clear` → 76
- `allocation_debated` → 42
- `active_ratepayer_backlash` → 12
- `unknown` → —

**Sources:** `puc_dockets`, `state_regulator_filings`, `local_news_search`

The fastest-growing category of data center opposition, and structurally different from noise or water complaints because it mobilizes ratepayers who live nowhere near the site. Several US states opened proceedings in 2024-2026 on whether large loads should bear their own grid costs. A site in a jurisdiction with clear cost-causation rules and a signed large-load tariff is materially de-risked; a site in a jurisdiction actively litigating the question carries an open-ended liability that should be surfaced to an investment committee rather than buried.

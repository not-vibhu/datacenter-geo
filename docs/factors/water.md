# Water factors

*Generated from `factors/water.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `wtr.basin_stress` Baseline water stress | ratio | A | 8 | 4 | 6 | gate.water_viable |
| `wtr.supply_availability` Physical water supply availability | m3_per_day | C | 7 | 4 | 6 |  |
| `wtr.reclaimed_availability` Reclaimed water availability | km_to_wwtp | B | 6 | 2 | 4 |  |
| `wtr.withdrawal_permitting` Water rights and withdrawal permitting | category | C | 7 | 3 | 5 | gate.water_viable |
| `wtr.wetbulb_profile` Wet-bulb temperature profile | hours_above_24C_wetbulb | A | 7 | 5 | 6 |  |
| `wtr.discharge_permitting` Blowdown and thermal discharge permitting | category | C | 5 | 2 | 4 |  |
| `wtr.flood_of_water_infrastructure` Water infrastructure resilience | index_0_100 | B | 4 | 2 | 3 |  |

## Baseline water stress

`wtr.basin_stress` · **ratio** · lower_is_better · best obtainable tier **A**

> What fraction of available renewable supply is already withdrawn in this basin?

**Normalization curve** (value → score):

| 0 | 0.1 | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 | 2.0 |
|---|---|---|---|---|---|---|---|
| 100 | 92 | 82 | 60 | 40 | 20 | 8 | 0 |

**Sources:** `wri_aqueduct_40`, `fao_aquastat`

WRI Aqueduct 4.0 is the global standard and is genuinely Tier A — a versioned raster with documented methodology. Use the baseline stress indicator plus the 2030 and 2050 projections under a business-as-usual scenario; a site that is fine today and extremely high stress in 2040 is a bad 25-year asset. High basin stress does not automatically disqualify: air-cooled and closed-loop designs operate in the Arizona and Nevada deserts. It disqualifies *evaporative* designs, and it raises political risk sharply regardless of design.

## Physical water supply availability

`wtr.supply_availability` · **m3_per_day** · higher_is_better · best obtainable tier **C**

> Is there a deliverable supply of the required volume, and from where?

**Normalization curve** (value → score):

| 0 | 500 | 2000 | 5000 | 12000 | 30000 |
|---|---|---|---|---|---|
| 0 | 25 | 50 | 72 | 88 | 100 |

**Sources:** `municipal_utility_reports`, `usgs_nwis`, `cgwb_india`, `provincial_water_cn`

Distinguish four sources and record which one the number refers to: municipal potable, raw surface withdrawal, groundwater, and reclaimed/recycled. They have completely different costs, permit pathways, and political optics. A 100 MW evaporatively-cooled facility runs roughly 1,500-2,500 m3/day depending on climate; state the load and cooling assumption alongside the requirement or the number is meaningless.

## Reclaimed water availability

`wtr.reclaimed_availability` · **km_to_wwtp** · lower_is_better · best obtainable tier **B**

> Is treated effluent available at sufficient volume and acceptable distance?

**Normalization curve** (value → score):

| 0 | 2 | 5 | 10 | 20 | 40 | 80 |
|---|---|---|---|---|---|---|
| 100 | 92 | 80 | 62 | 38 | 15 | 0 |

**Sources:** `osm_wastewater`, `epa_cwns`, `municipal_utility_reports`

Reclaimed water is the highest-leverage water intervention available to a data center developer: it neutralizes most community opposition, is usually cheaper per unit than potable, and is often actively encouraged by the municipality. Capture WWTP treated flow capacity, not just distance — a 5 km plant producing 800 m3/day cannot serve a 2,000 m3/day load. Pipeline cost is in the cost model and this factor frequently produces the best score-per-dollar recommendation in the entire system.

## Water rights and withdrawal permitting

`wtr.withdrawal_permitting` · **category** · categorical · best obtainable tier **C**

> How hard is it to obtain the legal right to the required volume?

**Categories:**

- `unrestricted_or_allocated` → 100
- `routine_permit` → 78
- `contested_but_available` → 50
- `severely_constrained` → 22
- `unavailable` → 0
- `unknown` → —

**Sources:** `state_water_authority`, `cgwb_india`, `provincial_water_cn`, `basin_authority_filings`

Legal availability and physical availability are different questions and the legal one kills more projects. Prior-appropriation states in the US West, adjudicated basins, and India's CGWB notified over-exploited blocks all have water physically present that you cannot lawfully take. In India, check whether the district is a CGWB "over-exploited" or "critical" block — groundwater abstraction there requires central authority clearance that is frequently denied for industrial use.

## Wet-bulb temperature profile

`wtr.wetbulb_profile` · **hours_above_24C_wetbulb** · lower_is_better · best obtainable tier **A**

> How many hours per year exceed the free-cooling wet-bulb threshold?

**Normalization curve** (value → score):

| 0 | 100 | 300 | 700 | 1200 | 2000 | 3000 | 4000 |
|---|---|---|---|---|---|---|---|
| 100 | 92 | 80 | 62 | 42 | 20 | 5 | 0 |

**Sources:** `era5_reanalysis`, `open_meteo_archive`, `nasa_power`

This is the physically correct driver of cooling energy and water consumption, and it is one of the few factors where a genuinely precise Tier-A answer is available anywhere on Earth from reanalysis data. Compute from hourly temperature and relative humidity over a 10-year window; report the design wet-bulb (0.4% exceedance, per ASHRAE convention) alongside the annual hours. Feed directly into the PUE/WUE model rather than scoring it in isolation.

## Blowdown and thermal discharge permitting

`wtr.discharge_permitting` · **category** · categorical · best obtainable tier **C**

> Can cooling blowdown be discharged legally and affordably?

**Categories:**

- `sewer_capacity_available` → 100
- `permit_routine` → 80
- `permit_constrained` → 48
- `zero_liquid_discharge_required` → 25
- `infeasible` → 0
- `unknown` → —

**Sources:** `epa_npdes`, `state_environmental_agency`, `cpcb_india`, `mee_china`

Frequently overlooked in early screening and expensive to discover late. Blowdown carries concentrated dissolved solids and treatment chemicals. Where zero-liquid-discharge is mandated, add $8-20 M capex and material opex to the cooling system — the Recommender should price this, not just flag it.

## Water infrastructure resilience

`wtr.flood_of_water_infrastructure` · **index_0_100** · higher_is_better · best obtainable tier **B**

> Is the water supply itself exposed to drought or failure?

**Normalization curve** (value → score):

| 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|
| 0 | 25 | 50 | 75 | 100 |

**Sources:** `wri_aqueduct_40`, `us_drought_monitor`, `imd_india`

Combines interannual variability, drought frequency, and dependence on a single source. A site with adequate average supply but high interannual variability needs on-site storage — cheap to build, expensive to retrofit, and rarely considered in early screening.

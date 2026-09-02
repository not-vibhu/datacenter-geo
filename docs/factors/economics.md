# Economics factors

*Generated from `factors/economics.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `eco.construction_labor` Construction labor availability | index_0_100 | C | 7 | 4 | 5 |  |
| `eco.construction_cost_index` Construction cost index | index_100_baseline | B | 5 | 5 | 5 |  |
| `eco.equipment_lead_time` Critical equipment lead time | months | C | 7 | 5 | 6 |  |
| `eco.port_rail_access` Port and rail access | km_to_capable_port_or_rail | A | 4 | 2 | 3 |  |
| `eco.operations_labor` Operations talent pool | index_0_100 | C | 4 | 5 | 5 |  |
| `eco.total_cost_of_ownership` Modeled 10-year TCO | USD_per_kW_year | D | 8 | 7 | 8 |  |

## Construction labor availability

`eco.construction_labor` · **index_0_100** · higher_is_better · best obtainable tier **C**

> Is there sufficient skilled electrical and mechanical trade capacity in the market?

**Normalization curve** (value → score):

| 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|
| 0 | 25 | 50 | 75 | 100 |

**Sources:** `bls_oes`, `union_local_data`, `state_labor_dept`, `national_labor_stats`

Electricians are the binding trade for data center construction. Markets with several concurrent large campuses experience real wage inflation and schedule slip — Northern Virginia, Phoenix, and Columbus have all shown this. Measure the count of electricians within commuting distance *against concurrent committed data center construction in the same market*, not in isolation; an absolute count without the demand side is misleading.

## Construction cost index

`eco.construction_cost_index` · **index_100_baseline** · lower_is_better · best obtainable tier **B**

> How expensive is building here relative to a national baseline?

**Normalization curve** (value → score):

| 60 | 80 | 95 | 105 | 120 | 140 | 180 |
|---|---|---|---|---|---|---|
| 100 | 90 | 76 | 62 | 42 | 20 | 0 |

**Sources:** `rsmeans_paid`, `turner_cost_index`, `national_construction_stats`

Shell and civil costs vary regionally by 30-50%; electrical and mechanical equipment is globally priced and varies far less. Since electrical and mechanical dominate data center cost, a high regional construction index hurts less than it would for a warehouse or an office. Apply the index to the civil and shell portion only, and say so — applying it to total project cost, as generic cost indices invite, materially overstates its effect.

## Critical equipment lead time

`eco.equipment_lead_time` · **months** · lower_is_better · best obtainable tier **C**

> Lead time for transformers, switchgear, generators and chillers to this market.

**Normalization curve** (value → score):

| 0 | 12 | 24 | 36 | 48 | 72 | 96 |
|---|---|---|---|---|---|---|
| 100 | 88 | 70 | 50 | 30 | 8 | 0 |

**Sources:** `industry_lead_time_surveys`, `manufacturer_guidance`, `trade_press`

Large power transformers have run 2-4 year lead times through the mid-2020s and are the most common cause of energization slip after interconnection itself. This is mostly a market-level rather than a site-level factor, but it varies by country through import duties, standards (IEC vs ANSI), and manufacturer regional allocation. Domestic manufacturing capacity in-country materially improves it — relevant for India (BHEL and others) and China.

## Port and rail access

`eco.port_rail_access` · **km_to_capable_port_or_rail** · lower_is_better · best obtainable tier **A**

> Can heavy imported equipment reach the site efficiently?

**Normalization curve** (value → score):

| 0 | 25 | 75 | 200 | 500 | 1000 | 2000 |
|---|---|---|---|---|---|---|
| 100 | 92 | 80 | 60 | 35 | 12 | 0 |

**Sources:** `osm_ports`, `osm_railways`, `world_port_index`

Matters most where major equipment is imported, which is the normal case outside the US and China. Read together with lnd.heavy_haul_access: a nearby port is worthless if the final 20 km cannot carry a 300 tonne load. Inland sites served by heavy-lift-capable rail are often better than coastal sites without it.

## Operations talent pool

`eco.operations_labor` · **index_0_100** · higher_is_better · best obtainable tier **C**

> Can the facility be staffed and kept staffed?

**Normalization curve** (value → score):

| 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|
| 0 | 25 | 50 | 75 | 100 |

**Sources:** `bls_oes`, `census_acs`, `local_university_programs`, `national_labor_stats`

Permanent headcount is small, so absolute pool size matters less than the presence of a technical training pipeline (community college or ITI programs, military bases, existing DC operators nearby). Remote and rural sites can be staffed successfully but carry higher retention risk and higher travel cost for specialist maintenance, which should be priced rather than scored away.

## Modeled 10-year TCO

`eco.total_cost_of_ownership` · **USD_per_kW_year** · lower_is_better · best obtainable tier **D**

> All-in modeled cost per kW-year across power, land, construction, tax and ops.

**Normalization curve** (value → score):

| 200 | 350 | 500 | 700 | 950 | 1300 | 2000 |
|---|---|---|---|---|---|---|
| 100 | 88 | 72 | 52 | 30 | 10 | 0 |

**Sources:** `derived`

A derived factor: composed from measured power price, land price, construction index, tax package, labor, and the PUE implied by the climate factors. It is Tier D by construction because it inherits every upstream uncertainty, and it must be presented as a range with the dominant sensitivity named — which is almost always power price. Do not let this factor's apparent precision obscure that. Its value is comparative, not absolute: a TCO delta between two sites computed the same way is meaningful even when the absolute number is not.

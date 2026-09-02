# Land factors

*Generated from `factors/land.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `lnd.contiguous_area` Contiguous developable area | hectares | B | 9 | 6 | 5 | gate.land_sufficient |
| `lnd.slope` Terrain slope | percent_slope | A | 6 | 4 | 3 |  |
| `lnd.price` Land acquisition cost | USD_per_hectare | D | 5 | 6 | 4 |  |
| `lnd.zoning_status` Zoning and entitlement status | category | B | 8 | 7 | 6 | gate.entitlement_path_exists |
| `lnd.protected_overlap` Protected area and habitat overlap | percent_overlap | A | 6 | 5 | 4 | gate.protected_exclusion |
| `lnd.brownfield_opportunity` Brownfield and retired-asset opportunity | category | B | 6 | 3 | 5 |  |
| `lnd.geotechnical` Geotechnical suitability | index_0_100 | C | 4 | 3 | 3 |  |
| `lnd.heavy_haul_access` Heavy haul road access | km_to_qualified_route | C | 5 | 2 | 3 |  |

## Contiguous developable area

`lnd.contiguous_area` · **hectares** · higher_is_better · best obtainable tier **B**

> Largest contiguous buildable area available at the site.

**Normalization curve** (value → score):

| 0 | 4 | 10 | 40 | 100 | 250 | 600 |
|---|---|---|---|---|---|---|
| 0 | 12 | 28 | 55 | 78 | 92 | 100 |

**Sources:** `esa_worldcover`, `copernicus_clc`, `osm_landuse`, `srtm_slope`, `county_parcel_gis`

Computed by masking out slope above threshold, water bodies, protected areas, built-up land, and known infrastructure, then finding the largest connected component. This yields *physically* developable area, which is an upper bound on *acquirable* area — parcel fragmentation and unwilling sellers routinely cut it by half or more. Always report both the computed figure and the caveat. In India in particular, land aggregation across many small holdings is often the binding constraint and is why state industrial corporation land (MIDC, SIPCOT, TSIIC, GIDC) commands a large premium in practice.

## Terrain slope

`lnd.slope` · **percent_slope** · lower_is_better · best obtainable tier **A**

> Mean and 90th-percentile slope across the developable area.

**Normalization curve** (value → score):

| 0 | 1 | 2 | 4 | 7 | 12 | 20 | 30 |
|---|---|---|---|---|---|---|---|
| 100 | 98 | 94 | 84 | 65 | 38 | 12 | 0 |

**Sources:** `srtm_30m`, `copernicus_dem_30m`, `alos_world3d`

Below 2% is essentially free. Each additional percent adds earthwork cost roughly quadratically for a large flat-pad campus. Report cut/fill volume estimate rather than slope alone where the DEM resolution supports it — that is the number an EPC will price. Copernicus 30 m DEM is the best free global option; SRTM has known voids above 60° latitude.

## Land acquisition cost

`lnd.price` · **USD_per_hectare** · lower_is_better · best obtainable tier **D**

> Expected all-in acquisition cost per hectare.

**Normalization curve** (value → score):

| 1000 | 10000 | 50000 | 150000 | 400000 | 1000000 | 3000000 |
|---|---|---|---|---|---|---|
| 100 | 90 | 74 | 55 | 34 | 14 | 0 |

**Sources:** `county_assessor`, `costar_paid`, `reonomy_paid`, `state_industrial_corp`, `regional_comparables`

Almost always Tier D outside US counties that publish assessor data. Report as a range with an explicit basis (assessed value, listed comparables, or state industrial allotment rate) and never as a point estimate. Land is usually 2-6% of total project cost for a hyperscale campus, so precision here matters far less than precision on power — resist the temptation to over-invest in it. Note that a data center rumor measurably moves local land prices, so pre-announcement comparables systematically understate acquisition cost.

## Zoning and entitlement status

`lnd.zoning_status` · **category** · categorical · best obtainable tier **B**

> Is the current zoning compatible, and if not, how hard is the path?

**Categories:**

- `by_right_industrial` → 100
- `industrial_with_sup` → 80
- `rezoning_routine` → 55
- `rezoning_contested` → 28
- `incompatible` → 5
- `unknown` → —

**Sources:** `county_zoning_gis`, `municipal_code`, `state_industrial_corp`, `provincial_land_use_cn`

By-right industrial zoning is worth an enormous amount and is the reason developers pay large premiums for pre-entitled land. A discretionary rezoning converts a technical problem into a political one, which is where com.opposition_risk becomes decisive. In several US jurisdictions since 2024, data centers have been removed from by-right industrial use — check the current code text, not a secondary summary.

## Protected area and habitat overlap

`lnd.protected_overlap` · **percent_overlap** · lower_is_better · best obtainable tier **A**

> Does the site intersect protected areas, wetlands, or critical habitat?

**Normalization curve** (value → score):

| 0 | 1 | 5 | 15 | 30 | 50 |
|---|---|---|---|---|---|
| 100 | 80 | 50 | 22 | 6 | 0 |

**Sources:** `wdpa_protected_planet`, `ramsar`, `nwi_wetlands`, `key_biodiversity_areas`, `forest_clearance_india`

Also check buffer zones, which frequently extend regulatory reach well beyond the mapped boundary. In India, any forest land — including degraded land classified as forest — triggers Forest (Conservation) Act clearance, which adds years and is a common and underappreciated cause of project failure. Wetland delineation in the US (Clean Water Act jurisdiction) has shifted with case law and should be verified against current agency guidance rather than assumed.

## Brownfield and retired-asset opportunity

`lnd.brownfield_opportunity` · **category** · categorical · best obtainable tier **B**

> Is this a retired industrial or generation site with reusable infrastructure?

**Categories:**

- `retired_power_plant` → 100
- `heavy_industrial_reuse` → 82
- `light_industrial_reuse` → 60
- `greenfield_clean` → 45
- `contaminated_remediation_needed` → 18
- `unknown` → —

**Sources:** `gem_retired_plants`, `epa_brownfields`, `eia_860_retirements`, `osm_industrial`

Retired and retiring coal plants are the single most valuable category of data center site in the current market, because they carry existing interconnection rights and transmission capacity — which converts a 5-7 year power problem into a 2-3 year one. This factor exists mainly to make the Prospector actively hunt for them. Offset against remediation cost and, at coal sites, coal ash management liability, which can be substantial.

## Geotechnical suitability

`lnd.geotechnical` · **index_0_100** · higher_is_better · best obtainable tier **C**

> Soil bearing capacity, karst, subsidence and shallow bedrock risk.

**Normalization curve** (value → score):

| 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|
| 0 | 25 | 50 | 75 | 100 |

**Sources:** `soilgrids_isric`, `usgs_karst`, `insar_subsidence`, `national_geological_survey`

Screening-level only. No global dataset substitutes for a geotechnical investigation, and this factor must never be presented as if it did. Its purpose is to flag karst terrain, high-plasticity clays, mining subsidence, and shallow groundwater early enough to affect site ranking. Karst is the most consequential flag — it can add tens of millions in foundation cost or make a site unbuildable.

## Heavy haul road access

`lnd.heavy_haul_access` · **km_to_qualified_route** · lower_is_better · best obtainable tier **C**

> Can 100+ tonne transformers physically reach the site?

**Normalization curve** (value → score):

| 0 | 2 | 5 | 15 | 30 | 60 | 120 |
|---|---|---|---|---|---|---|
| 100 | 94 | 85 | 65 | 42 | 18 | 0 |

**Sources:** `osm_highways`, `state_dot_permits`, `bridge_inventory_nbi`

A main generator step-up transformer can exceed 300 tonnes. Bridge weight limits, overhead clearances, and turning radii on the final approach are real constraints that have forced route rebuilds costing millions. Rail siding proximity is a strong mitigator and should be captured in the notes. This is a classic late-discovery problem: it is cheap to check early and expensive to discover after land acquisition.

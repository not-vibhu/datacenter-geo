# Climate factors

*Generated from `factors/climate.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `clm.dry_bulb_profile` Dry-bulb temperature profile and free-cooling hours | free_cooling_hours_per_year | A | 7 | 5 | 6 |  |
| `clm.extreme_heat_trend` Extreme heat trend to 2050 | delta_C_design_day_2050 | A | 5 | 4 | 5 |  |
| `clm.flood_riverine` Riverine and pluvial flood exposure | return_period_years | A | 8 | 7 | 8 | gate.flood_exclusion |
| `clm.flood_coastal` Coastal flood and sea level rise exposure | m_freeboard_2050 | A | 6 | 6 | 7 | gate.flood_exclusion |
| `clm.seismic` Seismic hazard | g_pga_475yr | A | 5 | 5 | 6 |  |
| `clm.wind_hazard` Extreme wind, cyclone and tornado hazard | design_wind_speed_ms | A | 4 | 4 | 5 |  |
| `clm.wildfire` Wildfire exposure | index_0_100 | A | 4 | 4 | 4 |  |
| `clm.air_quality` Ambient air quality | pm25_annual_ugm3 | A | 4 | 3 | 4 |  |
| `clm.lightning` Lightning density | flashes_per_km2_per_year | A | 2 | 2 | 2 |  |

## Dry-bulb temperature profile and free-cooling hours

`clm.dry_bulb_profile` · **free_cooling_hours_per_year** · higher_is_better · best obtainable tier **A**

> How many hours per year permit free (economizer) cooling?

**Normalization curve** (value → score):

| 0 | 1500 | 3000 | 5000 | 6500 | 7800 | 8760 |
|---|---|---|---|---|---|---|
| 0 | 22 | 42 | 65 | 82 | 95 | 100 |

**Sources:** `era5_reanalysis`, `open_meteo_archive`, `nasa_power`

Compute against the supply-air setpoint implied by the cooling assumption (default 27 °C for air-cooled IT, per ASHRAE A1 allowable). Free-cooling hours map almost linearly to annual PUE, which maps to opex — so this factor should be reported in dollars in the report, not just as a score.

## Extreme heat trend to 2050

`clm.extreme_heat_trend` · **delta_C_design_day_2050** · lower_is_better · best obtainable tier **A**

> How much does design-day temperature rise over the asset life?

**Normalization curve** (value → score):

| 0 | 0.5 | 1.0 | 1.5 | 2.0 | 3.0 | 4.5 | 6.0 |
|---|---|---|---|---|---|---|---|
| 100 | 92 | 82 | 68 | 52 | 28 | 5 | 0 |

**Sources:** `cmip6_nex_gddp`, `copernicus_cds`, `wri_climate_watch`

Use NEX-GDDP-CMIP6 downscaled projections under SSP2-4.5 as the base case and SSP5-8.5 as a stress case; report both. The practical consequence is chiller plant sizing: a plant sized to today's design day loses capacity headroom as design day rises, and derating a plant in year 15 is far more expensive than oversizing it in year 0.

## Riverine and pluvial flood exposure

`clm.flood_riverine` · **return_period_years** · higher_is_better · best obtainable tier **A**

> Does the site intersect a modeled flood zone, and at what return period?

**Normalization curve** (value → score):

| 0 | 50 | 100 | 200 | 500 | 1000 | 2000 |
|---|---|---|---|---|---|---|
| 0 | 8 | 25 | 55 | 82 | 96 | 100 |

**Sources:** `fathom_global`, `jrc_global_flood`, `fema_nfhl`, `wri_aqueduct_floods`

A hard gate at the 100-year floodplain and a strong penalty inside the 500-year. This is not primarily an engineering constraint — sites can be elevated — it is an insurance and financing constraint, and lenders apply it categorically. FEMA NFHL is authoritative in the US; JRC and WRI Aqueduct provide global coverage at coarser resolution, which is adequate for screening but must be confirmed with a local study before acquisition. Note that pluvial (flash) flooding is poorly captured by all global datasets and is a known blind spot.

## Coastal flood and sea level rise exposure

`clm.flood_coastal` · **m_freeboard_2050** · higher_is_better · best obtainable tier **A**

> Storm surge and 2050 sea level rise exposure.

**Normalization curve** (value → score):

| -2 | 0 | 1 | 3 | 6 | 10 | 20 |
|---|---|---|---|---|---|---|
| 0 | 10 | 35 | 65 | 85 | 96 | 100 |

**Sources:** `climate_central_coastal_dem`, `noaa_slr`, `wri_aqueduct_floods`

Only evaluated within 50 km of a coastline; scored N/A inland. Freeboard is site elevation minus projected 2050 100-year storm tide. Relevant to a surprising number of candidate sites because subsea cable landings and coastal population centers pull edge and colo facilities toward the coast.

## Seismic hazard

`clm.seismic` · **g_pga_475yr** · lower_is_better · best obtainable tier **A**

> Peak ground acceleration at 10% exceedance in 50 years.

**Normalization curve** (value → score):

| 0 | 0.05 | 0.1 | 0.2 | 0.3 | 0.5 | 0.8 | 1.2 |
|---|---|---|---|---|---|---|---|
| 100 | 95 | 88 | 72 | 55 | 30 | 8 | 0 |

**Sources:** `gem_global_seismic`, `usgs_hazard`, `is1893_india`, `gb18306_china`

Seismic hazard is a cost, not usually a barrier — Tokyo and Silicon Valley both host large data centers. Above 0.3 g expect a meaningful structural premium and significantly higher costs for raised floors, containment, and equipment anchoring. The Recommender should price the premium rather than penalizing the site twice. Report the national code zone alongside PGA, since local design practice is what the EPC will actually price against.

## Extreme wind, cyclone and tornado hazard

`clm.wind_hazard` · **design_wind_speed_ms** · lower_is_better · best obtainable tier **A**

> Design wind speed and severe convective exposure.

**Normalization curve** (value → score):

| 20 | 30 | 40 | 50 | 60 | 75 | 90 |
|---|---|---|---|---|---|---|
| 100 | 92 | 78 | 58 | 36 | 12 | 0 |

**Sources:** `gar_cyclone`, `noaa_storm_events`, `imd_cyclone`, `era5_reanalysis`

Separate tropical cyclone exposure from severe convective (tornado/hail) — they have different design responses and different insurance treatments. Hail is an underrated risk specifically because it destroys outdoor chiller and dry-cooler coils, which are on the roof and are the least-protected critical component in a modern air-cooled design.

## Wildfire exposure

`clm.wildfire` · **index_0_100** · lower_is_better · best obtainable tier **A**

> Wildfire hazard potential at and around the site.

**Normalization curve** (value → score):

| 0 | 10 | 25 | 45 | 65 | 85 | 100 |
|---|---|---|---|---|---|---|
| 100 | 92 | 78 | 58 | 35 | 12 | 0 |

**Sources:** `usfs_whp`, `global_fire_atlas`, `modis_burned_area`, `copernicus_effis`

The primary wildfire risk to a data center is not the building burning — it is smoke ingress fouling air-side economizers and filters, transmission line de-energization events (PSPS in California), and access road closure. Score accordingly: a site 5 km from high-hazard terrain has real operational exposure even if the structure itself is defensible.

## Ambient air quality

`clm.air_quality` · **pm25_annual_ugm3** · lower_is_better · best obtainable tier **A**

> Does particulate loading constrain air-side economization?

**Normalization curve** (value → score):

| 0 | 5 | 12 | 25 | 40 | 60 | 90 | 150 |
|---|---|---|---|---|---|---|---|
| 100 | 95 | 85 | 65 | 42 | 22 | 5 | 0 |

**Sources:** `openaq`, `cams_copernicus`, `cpcb_india`, `mee_china`

High PM2.5 forces higher-grade filtration (MERV 14+ or sealed designs), which costs fan energy and therefore PUE, and it can rule out air-side economization entirely. This factor is decisive in parts of northern India and northern China and is routinely omitted from Western-authored site selection frameworks — it is included here specifically because the tool is meant to work outside the US. Also check whether the airshed is a non-attainment zone, which affects the generator air permit; that is scored separately under reg.air_permit.

## Lightning density

`clm.lightning` · **flashes_per_km2_per_year** · lower_is_better · best obtainable tier **A**

> Flash density affecting surge protection and outage frequency.

**Normalization curve** (value → score):

| 0 | 1 | 4 | 10 | 20 | 40 | 80 | 150 |
|---|---|---|---|---|---|---|---|
| 100 | 96 | 88 | 72 | 52 | 25 | 5 | 0 |

**Sources:** `nasa_lis_otd`, `vaisala_gld360`

Low weight, cheaply measured, and mainly an input to surge protection design and to expected utility feed interruptions. Included for completeness; it should almost never change a decision on its own.

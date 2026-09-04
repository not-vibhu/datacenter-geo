# Site analysis — Hanover Ashland VA (APPROVED 2024)

**Hanover County, Virginia, United States** · `37.7400, -77.5100` · AOI radius 10 km
**Market:** PJM
**Run:** `run_0006` · 2026-09-03T05:13:31Z
**Cooling assumption:** hybrid_adiabatic

## Decision

### NOT PROVEN

Not yet — and the reason is missing evidence, not a bad site. 6 knockout checks cannot be evaluated at all because the factor each one reads is unmeasured; only 33% of the decision weight is measured. Profitability in particular is unanswerable here: 4 of 5 cost inputs are unmeasured (Modeled 10-year TCO, Industrial retail power price, Large-load tariff availability, Tax incentive package), so the score is a suitability screen, not a return. The verification queue is ordered by how much of the decision each answer settles.

*For profile `hyperscale_training`. Score 68 ± 16, confidence 0.25, 33% of decision weight measured.*

## Decision blockers

What stands between this evidence and a decision. Ranked by severity, then by the score points each one puts at risk.

| | Blocker | At risk | Who can close it |
|---|---|---|---|
| **FATAL** | Substation available capacity is unmeasured, and Credible power path to target load depends on it | 6 pts | Serving utility transmission planning |
| **FATAL** | Interconnection queue time to energization is unmeasured, and Credible power path to target load depends on it | 6 pts | ISO/RTO interconnection queue, then the utility |
| **FATAL** | Baseline water stress is unmeasured, and Water viability for the assumed cooling architecture depends on it | 5 pts | Water utility or basin regulator |
| **FATAL** | Water rights and withdrawal permitting is unmeasured, and Water viability for the assumed cooling architecture depends on it | 5 pts | State/provincial water regulator |
| **FATAL** | Coastal flood and sea level rise exposure is unmeasured, and Flood exclusion depends on it | 3 pts | Licensed civil / geotechnical engineer |
| **FATAL** | Protected area and habitat overlap is unmeasured, and Protected area exclusion depends on it | 2 pts | County or municipal planning department |
| **MAJOR** | Entitlement path exists | 4 pts | County/municipal planning department |
| **MINOR** | Modeled 10-year TCO is unmeasured | 7 pts | Owner's cost consultant |
| **MINOR** | Construction labor availability is unmeasured | 7 pts | Owner's cost consultant / EPC |
| **MINOR** | Critical equipment lead time is unmeasured | 7 pts | OEM / EPC procurement |
| **MINOR** | Permitting timeline is unmeasured | 7 pts | Local land-use counsel |
| **MINOR** | Environmental review burden is unmeasured | 6 pts | Local land-use counsel |
| **MINOR** | Tax incentive package is unmeasured | 6 pts | State/provincial economic development authority |
| **MINOR** | Industrial retail power price is unmeasured | 6 pts | Utility rate desk or wholesale market data provider |
| | *… 14 more* | | |

**Substation available capacity is unmeasured, and Credible power path to target load depends on it**

This gate is a knockout check and its input is missing, so its result is not evidence of anything. Resolving the factor moves the score by up to 6 points on its own.

- *Closes with:* Load-serving study or written statement of available capacity at the named substation, for the named load, in the named year.

- *Ask:* Serving utility transmission planning · typically 8–26 weeks

**Interconnection queue time to energization is unmeasured, and Credible power path to target load depends on it**

This gate is a knockout check and its input is missing, so its result is not evidence of anything. Resolving the factor moves the score by up to 6 points on its own.

- *Closes with:* Queue position and cluster study schedule for a comparable request
- *Ask:* ISO/RTO interconnection queue, then the utility · typically 4–12 weeks

**Baseline water stress is unmeasured, and Water viability for the assumed cooling architecture depends on it**

This gate is a knockout check and its input is missing, so its result is not evidence of anything. Resolving the factor moves the score by up to 5 points on its own.

- *Closes with:* Will-serve letter or withdrawal permit precedent
- *Ask:* Water utility or basin regulator · typically 8–26 weeks

**Water rights and withdrawal permitting is unmeasured, and Water viability for the assumed cooling architecture depends on it**

This gate is a knockout check and its input is missing, so its result is not evidence of anything. Resolving the factor moves the score by up to 5 points on its own.

- *Closes with:* Permit precedent for comparable industrial withdrawal in the same basin
- *Ask:* State/provincial water regulator · typically 10–30 weeks

**Coastal flood and sea level rise exposure is unmeasured, and Flood exclusion depends on it**

This gate is a knockout check and its input is missing, so its result is not evidence of anything. Resolving the factor moves the score by up to 3 points on its own.

- *Closes with:* Site-specific study; global rasters are screening-grade only
- *Ask:* Licensed civil / geotechnical engineer · typically 4–12 weeks

**Protected area and habitat overlap is unmeasured, and Protected area exclusion depends on it**

This gate is a knockout check and its input is missing, so its result is not evidence of anything. Resolving the factor moves the score by up to 2 points on its own.

- *Closes with:* Zoning determination letter and title/survey
- *Ask:* County or municipal planning department · typically 4–16 weeks

## What could flip the verdict

1 factor(s) can move the score across a verdict threshold on their own. Each row is the real scorer re-run with that one factor resolved at its best and worst plausible value, everything else held.

| Factor | State | Swing | Worst case | Best case |
|---|---|---|---|---|
| Accelerator export control exposure <br>`reg.export_controls` | tier B | ±14 | viable | strong-candidate |

## Verify next

Ordered by how much of the decision each answer settles. Gate-critical items come first regardless of points, because a knockout check that cannot be evaluated can make everything below it irrelevant.

1. **[gate]** **How much spare capacity (MVA) exists at the nearest suitable substation?**
   - `pwr.substation_headroom` · 6 points at risk · 8–26 weeks
   - **Ask:** Serving utility transmission planning
   - **Get:** Load-serving study or written statement of available capacity at the named substation, for the named load, in the named year.

   - *The single most common cause of a project dying after twelve months of work. Nothing published substitutes for the utility saying it in writing.*
2. **[gate]** **Realistic years from application to energization for target load.**
   - `pwr.interconnect_queue_time` · 6 points at risk · 4–12 weeks
   - **Ask:** ISO/RTO interconnection queue, then the utility
   - **Get:** Queue position and cluster study schedule for a comparable request
3. **[gate]** **What fraction of available renewable supply is already withdrawn in this basin?**
   - `wtr.basin_stress` · 5 points at risk · 8–26 weeks
   - **Ask:** Water utility or basin regulator
   - **Get:** Will-serve letter or withdrawal permit precedent
4. **[gate]** **How hard is it to obtain the legal right to the required volume?**
   - `wtr.withdrawal_permitting` · 5 points at risk · 10–30 weeks
   - **Ask:** State/provincial water regulator
   - **Get:** Permit precedent for comparable industrial withdrawal in the same basin
5. **[gate]** **Storm surge and 2050 sea level rise exposure.**
   - `clm.flood_coastal` · 3 points at risk · 4–12 weeks
   - **Ask:** Licensed civil / geotechnical engineer
   - **Get:** Site-specific study; global rasters are screening-grade only
6. **[gate]** **Does the site intersect protected areas, wetlands, or critical habitat?**
   - `lnd.protected_overlap` · 2 points at risk · 4–16 weeks
   - **Ask:** County or municipal planning department
   - **Get:** Zoning determination letter and title/survey
7. **All-in modeled cost per kW-year across power, land, construction, tax and ops.**
   - `eco.total_cost_of_ownership` · 7 points at risk · 6–16 weeks
   - **Ask:** Owner's cost consultant
   - **Get:** 10-year TCO model built on the confirmed tariff, land price and scope
   - *Depends on the tariff, land price and incentive answers above. It cannot be credibly modeled before them, which is why it is usually last in the queue and first in the investment memo.*
8. **Is there sufficient skilled electrical and mechanical trade capacity in the market?**
   - `eco.construction_labor` · 7 points at risk · 6–16 weeks
   - **Ask:** Owner's cost consultant / EPC
   - **Get:** Order-of-magnitude estimate against a real scope

## Scores by profile

| Profile | Verdict | Score | Confidence | Measured |
|---|---|---|---|---|
| `hyperscale_training` | **viable** *(capped by gate.power_path_exists)* | 68 ± 16 | 0.25 | 33% |
| `inference_edge` | **viable** *(capped by gate.power_path_exists)* | 68 ± 16 | 0.26 | 34% |
| `retrofit_colo` | **viable** *(capped by gate.power_path_exists)* | 68 ± 17 | 0.24 | 31% |

> **Insufficient evidence to publish a headline score** for `hyperscale_training`, `inference_edge`, `retrofit_colo` — measured fraction is below the configured minimum. Treat the numbers above as provisional.

## Gates

### Conditions

- **Credible power path to target load** (caps score at 68) — Substation available capacity is unknown — the most common cause of late-stage project failure. Verify with the utility before committing capital.
  - *Remediation:* Evaluate behind-the-meter generation, or shift target year, or reduce target load.
- **Water viability for the assumed cooling architecture** (caps score at 74) — Water availability and rights both unmeasured.
  - *Remediation:* Switch to air-cooled or closed-loop (costs 10-30% more power), or secure reclaimed water.
- **Entitlement path exists** (caps score at 72) — Requires discretionary rezoning (rezoning_routine) — this converts an engineering problem into a political one.
  - *Remediation:* Pre-application meeting with planning staff; budget 9-24 months and community engagement.
- **Protected area exclusion** (caps score at 82) — Protected-area overlap unmeasured.
  - *Remediation:* Reconfigure the site boundary to avoid overlap entirely — mitigation pathways are slow and uncertain.

### Cleared

- Flood exclusion — Outside the 500-year floodplain (modeled return period 1000 yr).
- Sufficient contiguous developable land — 2592 ha contiguous developable area (computed upper bound).
- No active data center moratorium — Community status: supportive_precedent.
- Intended compute is legally deployable — Export control status: unrestricted.

## Domain scores — `hyperscale_training`

| Domain | Score |
|---|---|
| power | 65 |
| water | 79 |
| connectivity | 81 |
| land | 84 |
| climate | 86 |
| economics | 99 |
| community | 100 |
| regulatory | 100 |

## Evidence ledger

Every scored factor, its measured value, and the tier of evidence behind it. A high score on Tier C/D evidence is a hypothesis, not a finding.

| Factor | Value | Unit | Score | Weight | Evidence | Source | Retrieved |
|---|---|---|---|---|---|---|---|
| Substation available capacity <br>`pwr.substation_headroom` | — | MVA | — | 10 | — (unmeasured) | — | — |
| Interconnection queue time to energization <br>`pwr.interconnect_queue_time` | — | years | — | 10 | — (unmeasured) | — | — |
| Contiguous developable area <br>`lnd.contiguous_area` | 2591.8 | hectares | 100 | 9 | C (researched) | `osm_overpass` | 2026-09-03 (0d) |
| Transmission line proximity <br>`pwr.transmission_proximity` | 3.97 | km | 89 | 9 | A (machine API) | `osm_overpass` | 2026-09-03 (0d) |
| Industrial retail power price <br>`pwr.retail_power_price` | — | USD/MWh | — | 9 | — (unmeasured) | — | — |
| Accelerator export control exposure <br>`reg.export_controls` | unrestricted | category | 100 | 9 | B (bulk/structured) | `bis_export_controls` | 2026-09-03 (0d) |
| Riverine and pluvial flood exposure <br>`clm.flood_riverine` | 1000 | return_period_years | 96 | 8 | A (machine API) | `fema_nfhl` | 2026-09-03 (0d) |
| Organized opposition risk <br>`com.opposition_risk` | supportive_precedent | category | 100 | 8 | C (researched) | `local_news_media` | 2026-09-03 (0d) |
| Modeled 10-year TCO <br>`eco.total_cost_of_ownership` | — | USD_per_kW_year | — | 8 | — (unmeasured) | — | — |
| Zoning and entitlement status <br>`lnd.zoning_status` | rezoning_routine | category | 55 | 8 | C (researched) | `us_local_government` | 2026-09-03 (0d) |
| Large-load tariff availability <br>`pwr.large_load_tariff` | — | category | — | 8 | — (unmeasured) | — | — |
| On-site generation potential <br>`pwr.onsite_generation_potential` | 39.3 | index_0_100 | 39 | 8 | C (researched) | `composite` | 2026-09-03 (0d) |
| Permitting timeline <br>`reg.permitting_timeline` | — | months | — | 8 | — (unmeasured) | — | — |
| Baseline water stress <br>`wtr.basin_stress` | — | ratio | — | 8 | — (unmeasured) | — | — |
| Dry-bulb temperature profile and free-cooling hours <br>`clm.dry_bulb_profile` | 6991.3 | free_cooling_hours_per_year | 87 | 7 | A (machine API) | `open_meteo_archive` | 2026-09-03 (0d) |
| Residential proximity and noise exposure <br>`com.residential_proximity` | 0 | dwellings_within_1km | 100 | 7 | C (researched) | `osm_overpass` | 2026-09-03 (0d) |
| Long-haul fiber proximity <br>`cnx.longhaul_fiber_proximity` | 12.11 | km | 64 | 7 | D (modeled) | `osm_overpass` | 2026-09-03 (0d) |
| Construction labor availability <br>`eco.construction_labor` | — | index_0_100 | — | 7 | — (unmeasured) | — | — |
| Critical equipment lead time <br>`eco.equipment_lead_time` | — | months | — | 7 | — (unmeasured) | — | — |
| Grid carbon intensity <br>`pwr.grid_carbon_intensity` | — | gCO2e/kWh | — | 7 | — (unmeasured) | — | — |
| Environmental review burden <br>`reg.environmental_review` | — | category | — | 7 | — (unmeasured) | — | — |
| Tax incentive package <br>`reg.tax_incentives` | — | index_0_100 | — | 7 | — (unmeasured) | — | — |
| Physical water supply availability <br>`wtr.supply_availability` | — | m3_per_day | — | 7 | — (unmeasured) | — | — |
| Water rights and withdrawal permitting <br>`wtr.withdrawal_permitting` | — | category | — | 7 | — (unmeasured) | — | — |
| Wet-bulb temperature profile <br>`wtr.wetbulb_profile` | 356.9 | hours_above_24C_wetbulb | 77 | 7 | A (machine API) | `open_meteo_archive` | 2026-09-03 (0d) |
| Coastal flood and sea level rise exposure <br>`clm.flood_coastal` | — | m_freeboard_2050 | — | 6 | — (unmeasured) | — | — |
| Ratepayer cost allocation sensitivity <br>`com.grid_cost_allocation` | — | category | — | 6 | — (unmeasured) | — | — |
| Physical path diversity <br>`cnx.path_diversity` | — | count_distinct_paths | — | 6 | — (unmeasured) | — | — |
| Terrain slope <br>`lnd.slope` | 0.76 | percent_slope | 98 | 6 | A (machine API) | `opentopography` | 2026-09-03 (0d) |
| Protected area and habitat overlap <br>`lnd.protected_overlap` | — | percent_overlap | — | 6 | — (unmeasured) | — | — |
| Brownfield and retired-asset opportunity <br>`lnd.brownfield_opportunity` | — | category | — | 6 | — (unmeasured) | — | — |
| Nodal congestion and basis volatility <br>`pwr.wholesale_basis_risk` | — | USD/MWh_stddev | — | 6 | — (unmeasured) | — | — |
| Grid reliability <br>`pwr.grid_reliability` | — | SAIDI_minutes_per_year | — | 6 | — (unmeasured) | — | — |
| Dispatchable generation within 50 km <br>`pwr.firm_capacity_nearby` | — | MW | — | 6 | — (unmeasured) | — | — |
| Clean power procurement market depth <br>`pwr.renewable_procurement_depth` | — | index_0_100 | — | 6 | — (unmeasured) | — | — |
| Generator air permitting <br>`reg.air_permit` | — | category | — | 6 | — (unmeasured) | — | — |
| Jurisdictional and political stability <br>`reg.jurisdiction_stability` | — | index_0_100 | — | 6 | — (unmeasured) | — | — |
| Reclaimed water availability <br>`wtr.reclaimed_availability` | 4.82 | km_to_wwtp | 81 | 6 | B (bulk/structured) | `osm_overpass` | 2026-09-03 (0d) |
| Extreme heat trend to 2050 <br>`clm.extreme_heat_trend` | 1.48 | delta_C_design_day_2050 | 69 | 5 | D (modeled) | `open_meteo_archive` | 2026-09-03 (0d) |
| Seismic hazard <br>`clm.seismic` | — | g_pga_475yr | — | 5 | — (unmeasured) | — | — |
| Local economic alignment <br>`com.economic_alignment` | — | index_0_100 | — | 5 | — (unmeasured) | — | — |
| Construction cost index <br>`eco.construction_cost_index` | — | index_100_baseline | — | 5 | — (unmeasured) | — | — |
| Land acquisition cost <br>`lnd.price` | 27500 | USD_per_hectare | 83 | 5 | C (researched) | `local_news_media` | 2026-09-03 (0d) |
| Heavy haul road access <br>`lnd.heavy_haul_access` | — | km_to_qualified_route | — | 5 | — (unmeasured) | — | — |
| Nuclear and SMR adjacency <br>`pwr.nuclear_smr_adjacency` | — | km | — | 5 | — (unmeasured) | — | — |
| Data sovereignty and cross-border regime <br>`reg.data_sovereignty` | — | category | — | 5 | — (unmeasured) | — | — |
| Blowdown and thermal discharge permitting <br>`wtr.discharge_permitting` | — | category | — | 5 | — (unmeasured) | — | — |
| Extreme wind, cyclone and tornado hazard <br>`clm.wind_hazard` | — | design_wind_speed_ms | — | 4 | — (unmeasured) | — | — |
| Wildfire exposure <br>`clm.wildfire` | — | index_0_100 | — | 4 | — (unmeasured) | — | — |
| Ambient air quality <br>`clm.air_quality` | — | pm25_annual_ugm3 | — | 4 | — (unmeasured) | — | — |
| Carrier availability <br>`cnx.carrier_count` | 38 | count_carriers | 100 | 4 | B (bulk/structured) | `peeringdb` | 2026-09-03 (0d) |
| Port and rail access <br>`eco.port_rail_access` | 2.44 | km_to_capable_port_or_rail | 99 | 4 | B (bulk/structured) | `osm_overpass` | 2026-09-03 (0d) |
| Operations talent pool <br>`eco.operations_labor` | — | index_0_100 | — | 4 | — (unmeasured) | — | — |
| Geotechnical suitability <br>`lnd.geotechnical` | — | index_0_100 | — | 4 | — (unmeasured) | — | — |
| Water infrastructure resilience <br>`wtr.flood_of_water_infrastructure` | — | index_0_100 | — | 4 | — (unmeasured) | — | — |
| Internet exchange and cloud on-ramp proximity <br>`cnx.ixp_proximity` | 7.94 | km | 96 | 3 | A (machine API) | `peeringdb` | 2026-09-03 (0d) |
| Lightning density <br>`clm.lightning` | — | flashes_per_km2_per_year | — | 2 | — (unmeasured) | — | — |
| Latency to demand centers <br>`cnx.latency_to_demand` | — | ms_rtt_p50 | — | 2 | — (unmeasured) | — | — |
| Subsea cable landing proximity <br>`cnx.subsea_landing` | — | km | — | 2 | — (unmeasured) | — | — |

*Every row carries where the number came from and when it was retrieved. A value marked `aging` or `stale` is past its source's declared refresh window and is discounted in the confidence figure accordingly.*

## Unmeasured (45)

These lowered the confidence score. Each is a specific, actionable research task.

- **Ambient air quality** (`clm.air_quality`) — no adapter implemented; Tier C research required (sources: openaq, cams_copernicus, cpcb_india)
- **Coastal flood and sea level rise exposure** (`clm.flood_coastal`) — no adapter implemented; Tier C research required (sources: climate_central_coastal_dem, noaa_slr, wri_aqueduct_floods)
- **Lightning density** (`clm.lightning`) — no adapter implemented; Tier C research required (sources: nasa_lis_otd, vaisala_gld360)
- **Seismic hazard** (`clm.seismic`) — no adapter implemented; Tier C research required (sources: gem_global_seismic, usgs_hazard, is1893_india)
- **Wildfire exposure** (`clm.wildfire`) — no adapter implemented; Tier C research required (sources: usfs_whp, global_fire_atlas, modis_burned_area)
- **Extreme wind, cyclone and tornado hazard** (`clm.wind_hazard`) — no adapter implemented; Tier C research required (sources: gar_cyclone, noaa_storm_events, imd_cyclone)
- **Latency to demand centers** (`cnx.latency_to_demand`) — no adapter implemented; Tier C research required (sources: ripe_atlas, cloudflare_radar, derived)
- **Physical path diversity** (`cnx.path_diversity`) — no adapter implemented; Tier C research required (sources: osm_telecom, carrier_route_maps, state_broadband_maps)
- **Subsea cable landing proximity** (`cnx.subsea_landing`) — no adapter implemented; Tier C research required (sources: telegeography_submarine_map, peeringdb)
- **Local economic alignment** (`com.economic_alignment`) — no adapter implemented; Tier C research required (sources: bls_local_unemployment, county_edc_priorities, census_acs)
- **Ratepayer cost allocation sensitivity** (`com.grid_cost_allocation`) — no adapter implemented; Tier C research required (sources: puc_dockets, state_regulator_filings, local_news_search)
- **Organized opposition risk** (`com.opposition_risk`) — no adapter implemented; Tier C research required (sources: local_news_search, county_meeting_minutes, change_org)
- **Construction cost index** (`eco.construction_cost_index`) — no adapter implemented; Tier C research required (sources: rsmeans_paid, turner_cost_index, national_construction_stats)
- **Construction labor availability** (`eco.construction_labor`) — no adapter implemented; Tier C research required (sources: bls_oes, union_local_data, state_labor_dept)
- **Critical equipment lead time** (`eco.equipment_lead_time`) — no adapter implemented; Tier C research required (sources: industry_lead_time_surveys, manufacturer_guidance, trade_press)
- **Operations talent pool** (`eco.operations_labor`) — no adapter implemented; Tier C research required (sources: bls_oes, census_acs, local_university_programs)
- **Modeled 10-year TCO** (`eco.total_cost_of_ownership`) — no adapter implemented; Tier C research required (sources: derived)
- **Brownfield and retired-asset opportunity** (`lnd.brownfield_opportunity`) — all Overpass mirrors failed: ReadTimeout: The read operation timed out
- **Geotechnical suitability** (`lnd.geotechnical`) — no adapter implemented; Tier C research required (sources: soilgrids_isric, usgs_karst, insar_subsidence)
- **Heavy haul road access** (`lnd.heavy_haul_access`) — no adapter implemented; Tier C research required (sources: osm_highways, state_dot_permits, bridge_inventory_nbi)
- **Land acquisition cost** (`lnd.price`) — no adapter implemented; Tier C research required (sources: county_assessor, costar_paid, reonomy_paid)
- **Protected area and habitat overlap** (`lnd.protected_overlap`) — no adapter implemented; Tier C research required (sources: wdpa_protected_planet, ramsar, nwi_wetlands)
- **Zoning and entitlement status** (`lnd.zoning_status`) — no adapter implemented; Tier C research required (sources: county_zoning_gis, municipal_code, state_industrial_corp)
- **Dispatchable generation within 50 km** (`pwr.firm_capacity_nearby`) — no adapter implemented; Tier C research required (sources: gem_power_plants, wri_powerwatch, eia_860)
- **Grid carbon intensity** (`pwr.grid_carbon_intensity`) — no adapter implemented; Tier C research required (sources: electricity_maps, ember_climate, epa_egrid)
- **Grid reliability** (`pwr.grid_reliability`) — no adapter implemented; Tier C research required (sources: eia_861_reliability, ceer_benchmarking, cea_india)
- **Interconnection queue time to energization** (`pwr.interconnect_queue_time`) — no adapter implemented; Tier C research required (sources: iso_queue_pjm, iso_queue_ercot, iso_queue_miso)
- **Large-load tariff availability** (`pwr.large_load_tariff`) — no adapter implemented; Tier C research required (sources: utility_tariff_filings, puc_dockets, state_regulator_cn)
- **Nuclear and SMR adjacency** (`pwr.nuclear_smr_adjacency`) — no adapter implemented; Tier C research required (sources: gem_nuclear, iaea_pris, nrc_applications)
- **Clean power procurement market depth** (`pwr.renewable_procurement_depth`) — no adapter implemented; Tier C research required (sources: lbnl_ppa_data, ember_climate, cleanenergybuyers)
- **Industrial retail power price** (`pwr.retail_power_price`) — no adapter implemented; Tier C research required (sources: eia_861, eia_electricity_data, ceic_cn)
- **Substation available capacity** (`pwr.substation_headroom`) — OSM does not publish substation capacity. Found 84 substation(s) within 40 km (73 at >=110 kV); nearest qualifying is Hanover Substation at 4.15 km, 230.0 kV. Headroom must be obtained from the utility's IRP or transmission planning study.
- **Nodal congestion and basis volatility** (`pwr.wholesale_basis_risk`) — no adapter implemented; Tier C research required (sources: ercot_lmp, pjm_dataminer, miso_lmp)
- **Generator air permitting** (`reg.air_permit`) — no adapter implemented; Tier C research required (sources: epa_nonattainment, state_air_agency, cpcb_india)
- **Data sovereignty and cross-border regime** (`reg.data_sovereignty`) — no adapter implemented; Tier C research required (sources: national_data_law, gdpr_adequacy, dpdp_india)
- **Environmental review burden** (`reg.environmental_review`) — no adapter implemented; Tier C research required (sources: nepa_ceq, state_env_agency, eia_notification_india)
- **Accelerator export control exposure** (`reg.export_controls`) — no adapter implemented; Tier C research required (sources: bis_entity_list, us_ear_ai_rules, eu_dual_use)
- **Jurisdictional and political stability** (`reg.jurisdiction_stability`) — no adapter implemented; Tier C research required (sources: world_bank_wgi, oecd_country_risk, eiu_democracy_index)
- **Permitting timeline** (`reg.permitting_timeline`) — no adapter implemented; Tier C research required (sources: county_permit_records, state_env_agency, moef_india)
- **Tax incentive package** (`reg.tax_incentives`) — no adapter implemented; Tier C research required (sources: state_statute, state_edc, state_dc_policy_india)
- **Baseline water stress** (`wtr.basin_stress`) — no adapter implemented; Tier C research required (sources: wri_aqueduct_40, fao_aquastat)
- **Blowdown and thermal discharge permitting** (`wtr.discharge_permitting`) — no adapter implemented; Tier C research required (sources: epa_npdes, state_environmental_agency, cpcb_india)
- **Water infrastructure resilience** (`wtr.flood_of_water_infrastructure`) — no adapter implemented; Tier C research required (sources: wri_aqueduct_40, us_drought_monitor, imd_india)
- **Physical water supply availability** (`wtr.supply_availability`) — no adapter implemented; Tier C research required (sources: municipal_utility_reports, usgs_nwis, cgwb_india)
- **Water rights and withdrawal permitting** (`wtr.withdrawal_permitting`) — no adapter implemented; Tier C research required (sources: state_water_authority, cgwb_india, provincial_water_cn)

## Provenance

| Tier | Measurements |
|---|---|
| A (machine API) | 6 |
| B (bulk/structured) | 4 |
| C (researched) | 6 |
| D (modeled) | 2 |
| — (unmeasured) | 45 |

**Sources used:** `bis_export_controls`, `composite`, `fema_nfhl`, `local_news_media`, `open_meteo_archive`, `opentopography`, `osm_overpass`, `peeringdb`, `us_local_government`

---

*Generated by [datacenter-geo](https://github.com/datacenter-geo/datacenter-geo). This is a screening tool. It tells you which sites deserve due diligence and what to ask when you get there. It does not replace due diligence.*

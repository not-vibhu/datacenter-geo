# Power factors

*Generated from `factors/power.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `pwr.transmission_proximity` Transmission line proximity | km | A | 9 | 7 | 6 |  |
| `pwr.substation_headroom` Substation available capacity | MVA | B | 10 | 8 | 9 | gate.power_path_exists |
| `pwr.interconnect_queue_time` Interconnection queue time to energization | years | B | 10 | 7 | 8 | gate.power_path_exists |
| `pwr.large_load_tariff` Large-load tariff availability | category | B | 8 | 5 | 7 |  |
| `pwr.retail_power_price` Industrial retail power price | USD/MWh | A | 9 | 6 | 8 |  |
| `pwr.wholesale_basis_risk` Nodal congestion and basis volatility | USD/MWh_stddev | B | 6 | 3 | 5 |  |
| `pwr.grid_carbon_intensity` Grid carbon intensity | gCO2e/kWh | A | 7 | 5 | 6 |  |
| `pwr.grid_reliability` Grid reliability | SAIDI_minutes_per_year | B | 6 | 7 | 7 |  |
| `pwr.onsite_generation_potential` On-site generation potential | index_0_100 | A | 8 | 4 | 5 |  |
| `pwr.firm_capacity_nearby` Dispatchable generation within 50 km | MW | A | 6 | 4 | 5 |  |
| `pwr.renewable_procurement_depth` Clean power procurement market depth | index_0_100 | C | 6 | 3 | 4 |  |
| `pwr.nuclear_smr_adjacency` Nuclear and SMR adjacency | km | A | 5 | 2 | 3 |  |

## Transmission line proximity

`pwr.transmission_proximity` · **km** · lower_is_better · best obtainable tier **A**

> Distance to the nearest transmission line of sufficient voltage to serve target load.

**Normalization curve** (value → score):

| 0 | 1 | 3 | 6 | 12 | 25 | 50 | 100 |
|---|---|---|---|---|---|---|---|
| 100 | 98 | 92 | 82 | 62 | 35 | 12 | 0 |

**Sources:** `openinframap`, `osm_overpass`, `gem_transmission`

Proximity is necessary but nowhere near sufficient — a line overhead with no available capacity is worth less than a line 15 km away with headroom. Always read alongside pwr.substation_headroom. For loads under 100 MW, 110-138 kV is usually adequate and the min_voltage_kv threshold should be lowered via --assume. OSM transmission coverage is excellent in Europe and North America, good in India, and patchy in parts of China and Africa — degrade tier to C and cross-check against Global Energy Monitor where OSM density looks implausible.

## Substation available capacity

`pwr.substation_headroom` · **MVA** · higher_is_better · best obtainable tier **B**

> How much spare capacity (MVA) exists at the nearest suitable substation?

**Normalization curve** (value → score):

| 0 | 50 | 100 | 200 | 400 | 800 | 1500 |
|---|---|---|---|---|---|---|
| 0 | 20 | 40 | 65 | 85 | 97 | 100 |

**Sources:** `utility_planning_docs`, `ferc_form_715`, `cea_india`, `iso_capacity_maps`

Rarely available as an API anywhere in the world. In the US, some utilities publish hosting-capacity maps (a distribution-level artifact, only partly applicable to transmission-served loads); most do not. Expect Tier B at best from utility integrated resource plans and transmission planning studies, Tier C commonly. Do not guess. An unknown here should push the site to CONDITIONAL, not to a midpoint score — this is precisely the factor most likely to kill a deal after twelve months of diligence.

## Interconnection queue time to energization

`pwr.interconnect_queue_time` · **years** · lower_is_better · best obtainable tier **B**

> Realistic years from application to energization for target load.

**Normalization curve** (value → score):

| 0 | 1 | 2 | 3 | 4 | 5 | 7 | 10 |
|---|---|---|---|---|---|---|---|
| 100 | 95 | 85 | 70 | 52 | 35 | 15 | 0 |

**Sources:** `iso_queue_pjm`, `iso_queue_ercot`, `iso_queue_miso`, `iso_queue_spp`, `iso_queue_caiso`, `lbnl_queued_up`, `cea_india`, `provincial_grid_cn`

The single most decisive factor in US site selection as of 2026, and the one most often misrepresented in marketing materials. Use the ISO's own published queue plus LBNL "Queued Up" historical completion statistics for the specific ISO — median *completed* time, not median *queued* time; the difference is large because most projects withdraw. ERCOT's connect-and-manage regime is structurally faster than PJM/MISO cluster studies and the scale must not be applied uniformly across ISOs without noting this. In India, use CEA/CTU connectivity timelines plus state DISCOM sanction time. In China, provincial grid company approval within a designated 东数西算 hub is materially faster than outside one.

## Large-load tariff availability

`pwr.large_load_tariff` · **category** · categorical · best obtainable tier **B**

> Does a tariff exist for loads of this size, and on what terms?

**Categories:**

- `established_favorable` → 100
- `established_neutral` → 78
- `negotiable` → 55
- `restrictive` → 28
- `hostile` → 5
- `unknown` → —

**Sources:** `utility_tariff_filings`, `puc_dockets`, `state_regulator_cn`, `serc_india`

An increasingly common deal-killer as utilities respond to load growth by imposing minimum-take obligations, collateral requirements, and exit fees on data center customers. Several US utilities filed restrictive large-load tariffs in 2024-2026. Check the PUC docket, not the utility's marketing page. In India the analogous question is open-access eligibility plus wheeling and banking charges, which vary by state and change annually.

## Industrial retail power price

`pwr.retail_power_price` · **USD/MWh** · lower_is_better · best obtainable tier **A**

> All-in delivered price for industrial-scale load.

**Normalization curve** (value → score):

| 20 | 35 | 50 | 70 | 90 | 120 | 180 | 250 |
|---|---|---|---|---|---|---|---|
| 100 | 92 | 80 | 62 | 42 | 20 | 3 | 0 |

**Sources:** `eia_861`, `eia_electricity_data`, `ceic_cn`, `cea_india`, `iea_prices`

At 400 MW and 90% utilization, a $10/MWh difference is roughly $31 M/year — which typically dwarfs every land and tax consideration in this model combined. Use state or provincial industrial average as the Tier-A baseline, then adjust to Tier C with the actual utility tariff where obtainable. Note whether the price includes transmission and rider charges; the headline number usually does not.

## Nodal congestion and basis volatility

`pwr.wholesale_basis_risk` · **USD/MWh_stddev** · lower_is_better · best obtainable tier **B**

> How volatile and congested is the local node relative to the hub?

**Normalization curve** (value → score):

| 0 | 5 | 10 | 20 | 35 | 60 | 100 |
|---|---|---|---|---|---|---|
| 100 | 88 | 72 | 50 | 28 | 8 | 0 |

**Sources:** `ercot_lmp`, `pjm_dataminer`, `miso_lmp`, `caiso_oasis`

Matters for merchant/hedged supply strategies and for anyone contemplating demand-response revenue. Irrelevant under a fixed-price bundled retail tariff — set weight to 0 via --weight when the supply strategy is known to be fixed. Only meaningful in liberalized markets; mark N/A in single-buyer markets.

## Grid carbon intensity

`pwr.grid_carbon_intensity` · **gCO2e/kWh** · lower_is_better · best obtainable tier **A**

> Average and marginal gCO2e per kWh of grid supply.

**Normalization curve** (value → score):

| 0 | 50 | 150 | 300 | 450 | 600 | 800 | 1000 |
|---|---|---|---|---|---|---|---|
| 100 | 95 | 82 | 62 | 42 | 22 | 6 | 0 |

**Sources:** `electricity_maps`, `ember_climate`, `epa_egrid`, `iea_emission_factors`

Report both average and marginal intensity; they diverge sharply and marginal is the honest number for a large new load. Hyperscaler procurement commitments (24/7 CFE, RE100) make this a hard requirement rather than a preference for some tenants — when the tenant is known to have a 24/7 CFE commitment, promote this to a gate via config. Note that carbon intensity and power price are strongly anti-correlated in several markets; the scoring model does not penalize this twice but a naive reader may double-count it.

## Grid reliability

`pwr.grid_reliability` · **SAIDI_minutes_per_year** · lower_is_better · best obtainable tier **B**

> Historical outage frequency and duration on the serving grid.

**Normalization curve** (value → score):

| 0 | 30 | 60 | 120 | 240 | 480 | 1000 | 2000 |
|---|---|---|---|---|---|---|---|
| 100 | 94 | 86 | 70 | 48 | 24 | 5 | 0 |

**Sources:** `eia_861_reliability`, `ceer_benchmarking`, `cea_india`, `world_bank_wgi`

Use SAIDI excluding major event days for the baseline and including them as a secondary figure — the difference tells you about weather exposure. Poor grid reliability is an economic penalty (more generator runtime, more fuel storage, higher N+ redundancy) rather than an absolute barrier, and the Recommender should price it as such.

## On-site generation potential

`pwr.onsite_generation_potential` · **index_0_100** · higher_is_better · best obtainable tier **A**

> Can the site self-supply or bridge with on-site generation?

**Composite of:**

- `gas_pipeline_distance_km` (weight 0.4, better=lower)
- `solar_ghi_kwh_m2_day` (weight 0.25, better=higher)
- `wind_capacity_factor` (weight 0.2, better=higher)
- `land_for_generation_ha` (weight 0.15, better=higher)

**Sources:** `osm_pipelines`, `gem_gas_infrastructure`, `nasa_power`, `global_wind_atlas`, `global_solar_atlas`

"Bring your own power" has become the dominant strategy for beating interconnection queues in the US. Gas pipeline proximity is the highest-signal component because behind-the-meter gas generation can be deployed in 18-30 months versus 4-7 years for grid interconnection. Solar and wind alone cannot firm a data center load and should never be scored as if they can — they are counted here for their contribution to a hybrid or bridging strategy, not as a standalone supply.

## Dispatchable generation within 50 km

`pwr.firm_capacity_nearby` · **MW** · higher_is_better · best obtainable tier **A**

> How much firm, dispatchable capacity sits electrically close to the site?

**Normalization curve** (value → score):

| 0 | 200 | 500 | 1000 | 2000 | 4000 | 8000 |
|---|---|---|---|---|---|---|
| 0 | 22 | 45 | 65 | 82 | 95 | 100 |

**Sources:** `gem_power_plants`, `wri_powerwatch`, `eia_860`, `cea_india`

Proximity to generation reduces transmission dependence and improves the odds of a favorable interconnection study result. Count only dispatchable capacity (gas, coal, nuclear, hydro with storage, geothermal); exclude variable renewables, which are counted in pwr.onsite_generation_potential instead. Retiring plants are a special case worth flagging: a retiring coal plant is an exceptional data center site because the interconnection rights, transmission, water rights, and often the land itself are already in place.

## Clean power procurement market depth

`pwr.renewable_procurement_depth` · **index_0_100** · higher_is_better · best obtainable tier **C**

> Can 24/7 or annually-matched clean power be procured at scale here?

**Normalization curve** (value → score):

| 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|
| 0 | 25 | 50 | 75 | 100 |

**Sources:** `lbnl_ppa_data`, `ember_climate`, `cleanenergybuyers`, `ireda_india`

Composite of: whether a liberalized PPA market exists at all, observed PPA volume in the market, availability of hourly-matched products, and REC/GO market liquidity. Largely Tier C — assembled from market reports rather than APIs. In India, evaluate state open-access rules specifically; national averages are misleading because banking and wheeling charges are set per state and have been tightened in several states since 2023.

## Nuclear and SMR adjacency

`pwr.nuclear_smr_adjacency` · **km** · lower_is_better · best obtainable tier **A**

> Distance to operating nuclear capacity or a credible announced SMR.

**Normalization curve** (value → score):

| 0 | 10 | 25 | 50 | 100 | 200 | 400 |
|---|---|---|---|---|---|---|
| 100 | 92 | 78 | 58 | 32 | 10 | 0 |

**Sources:** `gem_nuclear`, `iaea_pris`, `nrc_applications`

A low-weight but high-optionality factor. Co-location with nuclear offers firm carbon-free power and has driven several 2024-2026 US transactions. Score announced-but-unbuilt SMRs at Tier C or D with a heavy discount and record the announced COD explicitly — announced SMR dates have slipped consistently, and an analysis that credits an unbuilt SMR at face value is not credible.

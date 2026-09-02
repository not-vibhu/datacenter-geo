# Connectivity factors

*Generated from `factors/connectivity.yaml` — edit the YAML, not this file.*

| Factor | Unit | Best tier | hyperscale | inference | retrofit | Gate |
|---|---|---|---|---|---|---|
| `cnx.longhaul_fiber_proximity` Long-haul fiber proximity | km | B | 7 | 9 | 8 |  |
| `cnx.path_diversity` Physical path diversity | count_distinct_paths | C | 6 | 9 | 9 |  |
| `cnx.carrier_count` Carrier availability | count_carriers | C | 4 | 8 | 8 |  |
| `cnx.ixp_proximity` Internet exchange and cloud on-ramp proximity | km | A | 3 | 9 | 7 |  |
| `cnx.latency_to_demand` Latency to demand centers | ms_rtt_p50 | B | 2 | 10 | 8 |  |
| `cnx.subsea_landing` Subsea cable landing proximity | km | A | 2 | 6 | 5 |  |

## Long-haul fiber proximity

`cnx.longhaul_fiber_proximity` · **km** · lower_is_better · best obtainable tier **B**

> Distance to the nearest long-haul fiber route.

**Normalization curve** (value → score):

| 0 | 1 | 3 | 8 | 20 | 50 | 120 |
|---|---|---|---|---|---|---|
| 100 | 96 | 88 | 72 | 48 | 20 | 0 |

**Sources:** `osm_telecom`, `itu_transmission_maps`, `telegeography_paid`, `state_broadband_maps`

Open fiber route data is genuinely poor globally — carriers treat routes as confidential and OSM coverage is sparse and inconsistent. Use ITU transmission maps and state broadband maps where they exist, and infer from proxies (railway and highway rights-of-way, long-distance power line corridors) where they do not, marking the inference explicitly as Tier D. This factor's tier should be reported honestly rather than dressed up; it is one of the weakest data availability situations in the entire framework.

## Physical path diversity

`cnx.path_diversity` · **count_distinct_paths** · higher_is_better · best obtainable tier **C**

> How many physically distinct fiber routes serve this location?

**Normalization curve** (value → score):

| 0 | 1 | 2 | 3 | 4 | 6 |
|---|---|---|---|---|---|
| 0 | 25 | 62 | 82 | 92 | 100 |

**Sources:** `osm_telecom`, `carrier_route_maps`, `state_broadband_maps`

Two carriers sharing one conduit is one path, not two — this distinction is the whole point of the factor and is exactly what carrier sales materials obscure. Physical diversity means separate rights-of-way with meaningful geographic separation. Single-path sites are viable for training campuses and unacceptable for anything carrying production inference traffic.

## Carrier availability

`cnx.carrier_count` · **count_carriers** · higher_is_better · best obtainable tier **C**

> How many distinct network operators can deliver service on site?

**Normalization curve** (value → score):

| 0 | 1 | 2 | 3 | 5 | 8 | 12 |
|---|---|---|---|---|---|---|
| 0 | 22 | 48 | 66 | 84 | 95 | 100 |

**Sources:** `peeringdb`, `carrier_coverage_maps`, `state_broadband_maps`

Carrier count drives transit pricing more than it drives availability. A single carrier will serve almost any site given enough money; the question is what that money is. Where carrier count is low, the Recommender should price a fiber build to the nearest carrier-dense point rather than treating the site as unserved.

## Internet exchange and cloud on-ramp proximity

`cnx.ixp_proximity` · **km** · lower_is_better · best obtainable tier **A**

> Network distance to the nearest significant IXP or cloud on-ramp.

**Normalization curve** (value → score):

| 0 | 10 | 40 | 100 | 250 | 600 | 1500 |
|---|---|---|---|---|---|---|
| 100 | 95 | 85 | 68 | 45 | 20 | 2 |

**Sources:** `peeringdb`, `cloud_region_maps`, `packet_clearing_house`

PeeringDB is a genuinely good, free, machine-readable Tier-A source for IXPs and facilities. Weight this near zero for a training campus: the workload does not care, and over-weighting it biases the entire system toward expensive metro land, which is precisely the mistake this tool exists to prevent.

## Latency to demand centers

`cnx.latency_to_demand` · **ms_rtt_p50** · lower_is_better · best obtainable tier **B**

> Round-trip latency to the population and compute centers being served.

**Normalization curve** (value → score):

| 0 | 5 | 10 | 20 | 40 | 70 | 120 | 200 |
|---|---|---|---|---|---|---|---|
| 100 | 95 | 88 | 74 | 52 | 28 | 8 | 0 |

**Sources:** `ripe_atlas`, `cloudflare_radar`, `derived`, `ghsl_population`

Model as great-circle distance × 1.4 route factor × fiber propagation (approximately 4.9 µs/km) plus switching overhead, then validate against RIPE Atlas measurements where probes exist nearby. State which demand centers are being measured to — the answer is meaningless without that. For training campuses this factor is close to irrelevant and is weighted accordingly.

## Subsea cable landing proximity

`cnx.subsea_landing` · **km** · lower_is_better · best obtainable tier **A**

> Distance to a subsea cable landing station.

**Normalization curve** (value → score):

| 0 | 20 | 60 | 150 | 400 | 900 | 2000 |
|---|---|---|---|---|---|---|
| 100 | 92 | 78 | 58 | 32 | 10 | 0 |

**Sources:** `telegeography_submarine_map`, `peeringdb`

Decisive for international-facing capacity, near-irrelevant for domestic training. Highly relevant to India (Mumbai and Chennai landing clusters) and to any island or peninsular market. TeleGeography's public submarine cable map is free for non-commercial use and is accurate at the landing-station level.

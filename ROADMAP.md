# Roadmap

Honest status. The architecture and factor framework are complete; adapter coverage is
partial and that is the main gap between this and a production tool.

## Where it stands

| Layer | Status |
|---|---|
| Factor framework (59 factors, 8 domains) | Complete |
| Gates, profiles, scoring, confidence | Complete and tested |
| Agent + workflow layer | Complete |
| Adapters | ~13/59 factors machine-measured; rest is agent research |
| Validation set | 12 cases including 3 negative controls and 1 paired control |
| Hosted site | Not started |

## Next, in order of value

### 1. ISO interconnection queue parsers — highest value in the repo
`pwr.interconnect_queue_time` and `pwr.substation_headroom` are the two most decisive
factors and both are currently Tier C. Each ISO publishes a queue with a completely
different schema. Seven parsers (PJM, ERCOT, MISO, SPP, CAISO, NYISO, ISO-NE) would
move the single most important factor from C to B across two-thirds of US load.

This is unglamorous XLSX wrangling and it is worth more than everything else on this
list combined.

### 2. Raster pipeline for land and flood
`lnd.contiguous_area` is currently an OSM building-density heuristic (Tier C). The
correct implementation masks ESA WorldCover against slope, protected areas, and flood
zones, then finds the largest connected component. Same pipeline gives Tier A flood
from JRC/FEMA. Needs `rasterio` and either local tiles or Earth Engine.

### 3. FEMA NFHL and WRI Aqueduct adapters
Both are straightforward, both convert a currently-unmeasured gate input into Tier A,
and both are pure win. `gate.flood_exclusion` and `gate.water_viable` currently fire
CONDITIONAL on unknowns far too often.

### 4. Replace the heat projection placeholder
`clm.extreme_heat_trend` extrapolates an observed trend and is honestly labeled Tier D.
NEX-GDDP-CMIP6 is on S3 and free. This should be Tier A.

### 5. Self-hosted Overpass and geocoding
The public endpoints rate-limit bulk use, which caps sweeps at a few hundred tiles.
This is the binding constraint on scanning at scale.

Observed in practice: a single site analysis in a sparse-OSM region (Inner Mongolia)
took roughly 45 minutes against the public mirrors, almost entirely in query timeouts
that then returned very little. Client timeouts are now capped at 70 s per mirror so
these fail fast to `unknown` rather than stalling a run — but the real fix is a local
Overpass instance. Budget for this before attempting band 2 or 3 of the global sweep.

### 6. Cost model calibration
`data/reference/cost_models.yaml` carries industry-typical ranges assembled for
screening. Replacing any entry with a sourced, dated figure is the highest-value small
contribution available.

### 7. Hosted site with visualizations
Map view over `runs/*/site.geojson`, factor drill-down, scenario comparison, public
leaderboard. Reads the same JSON the CLI writes — no separate backend needed initially.

## Known limitations, stated plainly

- **No parcel-level ownership outside the US.** Cadastral data is not openly available
  in most jurisdictions. The system resolves to admin boundaries and says so.
- **Terrestrial fiber data is poor everywhere.** Carriers do not publish routes. This
  is the framework's weakest domain and no amount of engineering fixes it without a
  paid dataset.
- **Land price is Tier D almost everywhere.** Reported as a sourced range or omitted.
- **No prediction of utility behavior.** The system reports queue data and historical
  timelines. It does not claim to know what a utility will agree to.
- **Pluvial (flash) flooding is a blind spot** in every global flood dataset used here.
- **China and India coverage degrades** where OSM density is low. Tiers reflect this,
  but the honest answer is that US analyses are meaningfully better-founded than
  analyses elsewhere.

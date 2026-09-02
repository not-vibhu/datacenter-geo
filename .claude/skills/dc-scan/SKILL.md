---
name: dc-scan
description: Prospect a region for candidate data center sites by constraint intersection, generate falsifiable hypotheses, cheap-kill most of them, and promote survivors to full analysis. Use when the user wants to find sites rather than evaluate a known one.
---

# /dc-scan

Hypothesis generation across a region.

**Usage:** `/dc-scan "West Texas" --min-mw 300` · `/dc-scan --bbox "32.0,-102.5,33.5,-100.0"` · `/dc-scan "Telangana, India" --profile hyperscale_training`

## Steps

### 1. Frame the search — before any work
Do not scan without these. They change everything downstream:
- **Profile** — a training campus wants cheap remote land near power; an edge site
  wants expensive metro land near users. Scanning without knowing which produces a
  list nobody can use.
- **Target load and year**
- **Hard constraints** — country, state, distance from a city, existing holdings

### 2. Bound the region
Dispatch **parcel-resolver** with the region name to get a bounding box, or take
`--bbox` directly.

### 3. Coarse pass — arithmetic, not reasoning
```bash
uv run dcgeo scan --bbox "S,W,N,E" --step 10 --min-kv 230 --max-tiles 60
```
Thousands of tiles for near-zero cost. Do **not** reason about individual tiles here —
that is what makes it cheap.

### 4. Hypothesis generation
Dispatch **prospector** with the scan output. It clusters surviving tiles, hunts for
the high-value special cases the raster pass cannot see (retiring power plants, idled
heavy industry, incentive zones, stalled projects with live entitlements), and writes
one falsifiable hypothesis per candidate.

### 5. Cheap-kill
For each candidate, measure only the six highest-kill-rate factors before committing
to full analysis:

`pwr.interconnect_queue_time` · `lnd.contiguous_area` · `clm.flood_riverine` ·
`lnd.protected_overlap` · `com.opposition_risk` · `reg.export_controls`

Most candidates die here for ~5% of the cost of full analysis. **Be ruthless.** A scan
that promotes everything just moves cost downstream.

### 6. Promote
Run `/dc-analyze` on survivors, in priority order. Report the kill rate — if you
scanned 400 tiles and promoted 40, the constraints were too loose.

## Rules

- Coarse tile scores are **not** site scores. Never present them as such.
- State the kill rate explicitly.
- A hypothesis must name a mechanism ("4 km from the 500 kV corridor, inside the
  designated hub"), not attributes ("flat land near power").
- Budget awareness: full analysis of one site is minutes of agent time and dozens of
  API calls. Killing candidates early is the whole discipline.

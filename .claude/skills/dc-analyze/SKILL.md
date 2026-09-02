---
name: dc-analyze
description: Full site suitability analysis for a coordinate, address, parcel, or polygon. Resolves jurisdiction, runs adapters, fans out eight domain analysts in parallel, red-teams the result, scores it, and produces recommendations with costs. Use when the user gives a specific location to evaluate.
---

# /dc-analyze

Full analysis of one site. Roughly 10-25 minutes of agent time depending on how much
Tier C research the location requires.

**Usage:** `/dc-analyze 39.0437,-77.4875` · `/dc-analyze "Abilene, Texas" --profile hyperscale_training` · `/dc-analyze --geojson site.json`

## Steps

### 1. Resolve the site — never skip this
Dispatch **parcel-resolver**. Half the factors are jurisdiction-dependent and
meaningless without country, state, county, utility, and market (ISO/RTO, DISCOM, or
provincial grid). Analyzing a bare coordinate produces confidently wrong regulatory
and power output.

### 2. Establish the frame
Confirm with the user, or state your assumption explicitly and proceed:
- **Profile** — `hyperscale_training` (default), `inference_edge`, or `retrofit_colo`
- **Target load and energization year**
- **Cooling architecture** — default `hybrid_adiabatic`; `air_cooled` changes the
  water gate entirely

### 3. Run the deterministic pass
```bash
uv run dcgeo analyze --at LAT,LON --name "NAME" --radius 10 --cooling hybrid_adiabatic
```
This resolves context, runs every adapter, gates, scores, and writes `runs/run_NNNN/`.
It will report roughly 13 of 59 factors measured — that is expected. The adapters
cover what is machine-measurable; the analysts cover the rest.

### 4. Fan out the domain analysts — in parallel
Dispatch all eight in a **single message** with parallel Agent calls. They are
independent; running them serially wastes wall-clock time for no benefit.

`power-analyst` · `water-cooling-analyst` · `climate-hazard-analyst` · `land-analyst` ·
`connectivity-analyst` · `regulatory-analyst` · `community-analyst` · `economics-analyst`

Give each the run id, the coordinate, the resolved jurisdiction, and the frame from
step 2. Each researches its unmeasured factors and records them with
`dcgeo add-measurement`.

### 5. Red team
Dispatch **red-team** on the completed ledger. Never skip this, including on re-runs.
If it invalidates a measurement, send it back to the owning analyst and re-measure —
do not paper over it in the summary.

### 6. Re-score
```bash
uv run dcgeo score runs/run_NNNN
```
Dispatch **scorer** to interpret. If measured fraction is still below the floor, say
the score is provisional rather than presenting it as a finding.

### 7. Recommend
Dispatch **recommender** for gap → intervention → cost → leverage.

### 8. Audit before publishing
Dispatch **evidence-librarian** if this analysis will be shared externally or acted on.

### 9. Deliver
```bash
uv run dcgeo report runs/run_NNNN
```
Present: verdict and deal-killers first, then score with band, then the drivers, then
recommendations. Offer the artifact if the user wants a shareable version.

## Rules

- **Verdict before score.** Lead with what would kill this site.
- **Never present a provisional score as a finding.** If coverage is below the floor,
  say so in the first line.
- **Bands are not decoration.** `78 ± 9` and `71 ± 3` are not rankable and you must
  say so rather than sorting them.
- **Do not skip the red team** because the site looks good. That is precisely when
  optimism drift has occurred.

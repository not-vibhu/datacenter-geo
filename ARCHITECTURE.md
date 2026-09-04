# Architecture

## Design principles

**1. Evidence before score.** The score is a derived artifact. The primary output is
an *evidence ledger* — a list of claims, each with a value, a unit, a source, a
retrieval timestamp, and a tier. If the ledger is right, any scoring model can be
applied to it later. If the ledger is wrong, no scoring model saves you.

**2. Gates before weights.** Deal-killers are categorical, not continuous. They are
evaluated first and they short-circuit.

**3. Separate measurement from judgment.** Adapters measure. Agents judge. An adapter
returns "nearest 230 kV line: 6.2 km, source: OpenInfraMap, retrieved 2026-09-02".
An agent decides what that means for a 400 MW campus. These never mix — which is what
makes the numeric layer testable and the reasoning layer auditable.

**4. Every agent must be able to say "I don't know."** A missing measurement is
recorded as `unknown` with a reason, and it *lowers confidence* rather than silently
defaulting to a midpoint. The most common failure mode in scoring systems is treating
absence of evidence as evidence of adequacy.

**5. The red team is not optional.** An adversarial pass runs on every site before
scoring. Without it, LLM analysts drift toward optimism — they find reasons a site
works because that is the shape of the task they were given.

---

## Layers

```
┌────────────────────────────────────────────────────────────────┐
│  WORKFLOW LAYER          .claude/skills/*.md                   │
│  /dc-analyze  /dc-scan  /dc-rerun  /dc-compare  /dc-validate   │
│  Orchestration, fan-out, human-in-the-loop checkpoints         │
├────────────────────────────────────────────────────────────────┤
│  AGENT LAYER             .claude/agents/*.md                   │
│  Prospector · Parcel Resolver · 8 domain analysts · Red Team   │
│  Scorer · Recommender · Evidence Librarian                     │
│  Judgment, synthesis, Tier-C web research                      │
├────────────────────────────────────────────────────────────────┤
│  FACTOR LAYER            factors/*.yaml                        │
│  59 specs: formula, unit, direction, gate, scale, weights      │
│  The contract between agents and measurements                  │
├────────────────────────────────────────────────────────────────┤
│  DECISION LAYER          dcgeo/diligence.py  compare.py        │
│  Blockers · sensitivity · verification queue · the brief        │
│  Turns a score into "can this work, and what must be verified"  │
├────────────────────────────────────────────────────────────────┤
│  TOOL LAYER              dcgeo/  (Python CLI)                  │
│  measure · score · provenance · evidence · cache · geo · report │
│  Deterministic, testable, no LLM in the loop                   │
├────────────────────────────────────────────────────────────────┤
│  ADAPTER LAYER           dcgeo/adapters/*.py                   │
│  One module per external source. Uniform Measurement return.   │
│  Free sources active; paid sources stubbed behind key checks.  │
└────────────────────────────────────────────────────────────────┘
```

The boundary that matters is between the **factor layer** and everything else. A
factor spec is the single source of truth for what a metric means. Agents read it to
know what to research. The scoring engine reads it to know how to normalize. The docs
generator reads it to write the methodology page. Add a factor in one place and it
propagates everywhere.

---

## Data model

Four objects. Everything else is a view over them.

### Measurement
The atom. One number (or category) about one place, from one source, at one time.

```python
Measurement(
    factor_id   = "pwr.transmission_proximity",
    value       = 6.2,
    unit        = "km",
    tier        = "A",
    source      = "openinframap",
    source_url  = "https://openinframap.org/...",
    retrieved   = "2026-09-02T11:04:22Z",
    geometry_ref= "aoi:site_0031",
    confidence  = 0.95,
    notes       = "Nearest ≥230kV; 3 lines within 15km",
)
```

Measurements are immutable and cached by `(factor_id, geohash, source, params)`.
A re-run reuses cached measurements unless `--fresh` or the TTL in
`config/sources.yaml` has expired. This is what makes scanning 2,000 sites tractable.

### Claim
A judgment made *about* measurements by an agent. Carries its own citations, and
crucially, an explicit list of the measurement IDs it rests on — so a claim can be
invalidated automatically when its underlying measurement is refreshed and changes.

### Site
An area of interest: a polygon, a centroid, an admin context (country/state/county),
and a provenance record of how it was proposed (manual, prospector hypothesis, or
imported from the reference set).

### Analysis
One scoring run over one site: the measurement set, the claim set, gate results,
per-profile scores, confidence, red-team findings, and recommendations. Analyses are
append-only and versioned; a re-run creates a child analysis with a diff against its
parent, so you can see exactly what changed and why.

---

## The eight domains

| Domain | Factors | The question it answers |
|--------|---------|-------------------------|
| `power` | 12 | Can this site get 300–1000 MW, when, at what price, how clean? |
| `water` | 7 | Can it be cooled, legally and sustainably, year-round? |
| `climate` | 9 | What will nature do to it over a 25-year asset life? |
| `land` | 8 | Is there a big enough, buildable, acquirable, zonable parcel? |
| `connectivity` | 6 | Can bits get in and out, redundantly, fast enough? |
| `regulatory` | 7 | Will the state let it be built, and how long will that take? |
| `community` | 4 | Will the neighbours stop it? |
| `economics` | 6 | Can it actually be constructed and operated here? |

Full specs in `factors/`. Methodology narrative in `docs/factors/`.

---

## Scoring

### Stage 1 — Gates

Gates are boolean predicates over measurements. Three outcomes:

- `PASS` — proceed
- `CONDITIONAL` — proceed, but the condition becomes a mandatory recommendation with
  a cost attached, and the site cannot exceed `capped_score` until resolved
- `FAIL` — verdict is `NO-GO`; scoring still runs (so you can see *how close* it was
  and what would unlock it) but the headline verdict does not change

Defined in `config/gates.yaml`. Examples: no interconnection path to target MW before
target year; site intersects 100-year floodplain; active local data center moratorium;
protected-area overlap; PGA above threshold without seismic design premium.

A gate that fails on **Tier C or D evidence** produces `FAIL (low confidence)` and is
flagged for human verification rather than treated as settled. We do not kill sites
on the strength of a news article.

### Stage 2 — Normalization

Each factor maps its raw value to 0–100 via a piecewise-linear curve defined in its
spec. Piecewise, not linear — because these relationships have knees. Wet-bulb
temperature is nearly free below 18 °C and expensive above 24 °C; the curve encodes
that, and it is visible and arguable in the YAML rather than buried in code.

### Stage 3 — Profile weighting

Three profiles ship by default (`config/profiles.yaml`):

| | hyperscale_training | inference_edge | retrofit_colo |
|---|---|---|---|
| Target IT load | 300–1000 MW | 5–50 MW | 20–100 MW |
| Latency to users | irrelevant | **critical** | important |
| Water sensitivity | high | low | medium |
| Land requirement | 200–1500 acres | 2–15 acres | existing shell |
| Power price weight | **dominant** | moderate | high |

Domain score = weighted mean of its factors. Overall = weighted mean of domains.
Weights live in the factor specs, per profile, so adding a profile is a config change.

### Stage 4 — Confidence

Tier answers *how was this obtained*. It does not answer *is it still true*. So the
weight an individual datapoint carries is two-dimensional (`dcgeo/provenance.py`):

```
tier_weight     = {A: 1.00, B: 0.85, C: 0.60, D: 0.35, unknown: 0.0}
freshness       = age vs the source's declared ttl_days in sources.yaml
                  fresh 1.00 · aging 0.85 · stale 0.55 · undated 0.70
evidence_weight = tier_weight × freshness

confidence      = Σ(weight_i × evidence_weight_i) / Σ(weight_i)
band            = ±(1 − confidence) × 22        # empirical spread constant
```

Reported as `78 ± 9 (confidence 0.61)`. The band is not decoration — a site at
`78 ± 9` and one at `71 ± 3` are not meaningfully rankable, and the compare workflow
says so explicitly instead of sorting them.

A stale Tier-A number therefore reports lower confidence, and a wider band, than the
same number measured yesterday. Staleness costs exactly what a weaker tier costs,
because in practice it is the same problem.

---

## The decision layer

Scoring is the middle of the pipeline. `dcgeo/diligence.py` turns a `ProfileScore`
into a `DiligenceBrief` — the object the report, the CLI and the static site all
render. It is pure arithmetic over the evidence ledger; no LLM touches it.

### Blockers

Six kinds, deduplicated downward so the list is a set of actions rather than a set of
observations:

| Kind | Severity | Raised when |
|---|---|---|
| `gate_fail` | fatal | A knockout check failed on Tier A/B evidence |
| `gate_unverified` | fatal | A knockout check failed, but on Tier C/D evidence |
| `gate_undecidable` | fatal | The factor a knockout check reads is unmeasured |
| `domain_blackout` | fatal / major | A whole domain has no data and left the aggregate |
| `unknown_material` | major / minor | An unmeasured factor carrying material swing |
| `stale` / `weak_evidence` | major / minor | A measured value too old or too modeled to lean on |

A `domain_blackout` absorbs the individual unknowns inside it: "dispatch the
regulatory analyst" is one action, not seven. A `gate_condition` that exists only
because its input was missing is suppressed in favour of the `gate_undecidable` entry
naming the factor, which is the thing somebody can actually act on.

Every blocker carries an owner and an artifact, routed through
`config/verification.yaml`. That file is the difference between an unknown and an
actionable unknown — a system that reports a gap without naming the counterparty who
can close it has only relabelled the gap. Routing is jurisdictional: the counterparty
for a grid question in India is a DISCOM and a State Load Despatch Centre, not an ISO.

### Sensitivity

For each weighted factor, the score is recomputed with that one factor forced to 0 and
to 100, at the tier it would be measured at if somebody went and measured it properly.
The swing is the difference.

This runs **through `score_profile` itself**, via a `counterfactual` parameter, rather
than through a second implementation of the aggregation. A parallel formula would
drift from the scorer it claims to explain; this one cannot.

Gate outcomes turn on raw values rather than normalized ones, so simulating them would
mean inventing raw values. Instead, factors a gate reads are flagged `gate_critical`
and handled as blockers — a claim about what is undecided, not a fabricated scenario.

### The decision

```
NO-GO                    a fatal gate failed on evidence strong enough to act on
NOT PROVEN               fatal blockers remain, or an unmeasured factor could move
                         the verdict across a threshold on its own, or the measured
                         fraction is below the publishable floor
PROCEED WITH CONDITIONS  gates satisfied, major conditions outstanding
PROCEED                  gates satisfied, nothing unmeasured can flip the verdict
```

`NOT PROVEN` is the load-bearing state. It is the honest answer for most screening
work, and a system that cannot say it will say something worse instead.

Profitability is refused separately and explicitly: unless every factor in
`decision.profitability_factors` is measured, the brief states that the score is a
suitability screen and not a return. Suitability and profitability are different
questions and the score only answers one of them.

---

## Prospecting (hypothesis generation)

The Prospector does not search a database of parcels — no such global database
exists. It works by **constraint intersection**, coarse to fine:

1. **Coarse raster pass.** Tile the region (default 10 km). Cheaply score each tile on
   the four factors that are globally available as rasters or vector layers and that
   kill sites most often: transmission proximity, terrain slope, protected-area
   exclusion, and flood exclusion. This is arithmetic, not LLM work — thousands of
   tiles for near-zero cost.
2. **Cluster and rank.** Surviving tiles are clustered into contiguous candidate
   areas; areas below the minimum contiguous-acreage threshold for the profile are
   dropped.
3. **Hypothesis writing.** *Now* the LLM enters. For each surviving cluster the
   Prospector writes an explicit, falsifiable hypothesis: "Cluster T-14 can support
   400 MW by 2031 because it sits 4 km from the Ulanqab 500 kV corridor, in a county
   with an existing large-load tariff, on flat non-arable land." That sentence is the
   thing downstream analysts are tasked with disproving.
4. **Cheap-kill pass.** Analysts run only the 6 highest-kill-rate factors first. Most
   candidates die here for ~5% of the cost of a full analysis.
5. **Full analysis** on survivors.

Cost discipline matters: full analysis of one site is minutes of agent time and
dozens of API calls. Scanning a region means being ruthless about killing candidates
early and cheaply.

---

## Recommendations

For every factor scoring below its profile's threshold, the Recommender produces:

```
gap → intervention → cost → timeline → confidence → who must act
```

Costs come from `data/reference/cost_models.yaml` — parametric unit costs
(e.g. 230 kV transmission build at $1.8–3.2 M/mile depending on terrain and land
acquisition; 100 MVA substation at $18–35 M; reclaimed-water pipeline at
$1.2–2.4 M/mile) with explicit ranges and a stated basis year. **Every cost is a
range and every range is sourced.** A point estimate for a transmission build is a
fiction, and presenting one destroys trust in the whole report.

Recommendations are also scored for *leverage*: score-points gained per dollar. This
is what turns the tool from an assessment into a decision aid — it tells a developer
that $12 M of reclaimed-water pipeline buys more than $40 M of on-site generation.

---

## Re-running with different assumptions

```bash
dcgeo rerun run_0031 \
  --assume "interconnect_year=2029" \
  --assume "onsite_gas_ppa=true" \
  --weight water=0.4 \
  --profile inference_edge
```

Assumptions are injected as synthetic Tier-D measurements, clearly labeled as
assumed rather than measured, and they propagate through gates and scoring. The
output diff shows exactly which gates flipped and which factors moved. This is the
mechanism behind "what would it take to make this site work?" — and it is the same
mechanism the Recommender uses internally to price interventions.

---

## Scheduled sweeps

`crons/global-sweep.md` defines continuous discovery: the world is partitioned into
priority bands (active power-market regions with load growth first), and each cron
run advances the frontier, runs the coarse raster pass over the next tile batch,
promotes anything above threshold to full analysis, and appends to a global leaderboard.

Sweeps also **re-check** previously analyzed sites for state changes that invalidate
prior conclusions: new interconnection queue postings, moratorium enactments, drought
declarations, transmission project approvals. A site analysis is a perishable good;
the sweep is what keeps the corpus fresh.

---

## What this architecture deliberately does not do

- **No parcel-level ownership resolution outside the US.** Cadastral data is not
  openly available in most jurisdictions. The system resolves to admin boundaries and
  says so rather than fabricating parcels.
- **No prediction of utility behavior.** It reports queue data and historical
  timelines. It does not claim to know what a utility will agree to.
- **No single global land price model.** Land price is Tier D almost everywhere and is
  reported as a wide sourced range, or omitted.

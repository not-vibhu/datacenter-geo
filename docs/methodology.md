# Methodology

## What this system is claiming

That it can rank candidate locations for AI data centers, transparently, at a cost low
enough to evaluate hundreds rather than three — and that it will tell you honestly how
much of each ranking rests on measurement versus inference.

## What it is not claiming

- **Not a substitute for due diligence.** It tells you which twenty sites out of two
  thousand deserve diligence, and what to ask when you get there.
- **Not a predictor of utility or regulator behavior.** It reports queue data,
  published tariffs, and historical timelines. Nobody can tell you what a utility will
  agree to.
- **Not equally good everywhere.** US analyses are meaningfully better-founded than
  analyses elsewhere, because US data is better. The confidence score reflects this,
  and it should be read.

## The core design decisions

### 1. Evidence is the product; the score is derived

The primary artifact is the **evidence ledger** — every claim with a value, unit,
source, retrieval timestamp, and tier. If the ledger is right, any scoring model can be
applied to it later, including one the reader prefers to ours. If the ledger is wrong,
no scoring model saves you.

This is why `runs/*/analysis.json` contains every measurement, not just the score, and
why re-runs create children rather than overwriting.

### 2. Measurement and judgment never mix

Adapters measure: *"nearest 230 kV line: 6.2 km, OpenInfraMap, retrieved 2026-09-02."*
Agents judge: *"6.2 km is workable but the relevant question is Ashburn Substation's
headroom, which the utility has not published."*

Adapters are deterministic Python and are tested. Agents are LLM and are audited. Keeping
them separate is what makes the numeric layer trustworthy and the reasoning layer
reviewable. An adapter that "interprets" is a bug.

### 3. Absence of evidence is not evidence of adequacy

Covered fully in [evidence-tiers.md](evidence-tiers.md). Unknown is a recorded value
with a reason; it lowers confidence and can block publication.

### 4. The red team is not optional

LLM analysts drift toward optimism — they find reasons a site works, because that is the
shape of the task. An adversarial pass whose only job is to kill the site runs on every
analysis, including re-runs. Without it the output is a brochure.

### 5. Gates before weights

Deal-killers are categorical. See [scoring.md](scoring.md).

## Where the framework is weakest, stated plainly

| Weakness | Consequence |
|---|---|
| Terrestrial fiber routes are not public anywhere | `connectivity` route factors are C/D outside metros |
| Utilities do not publish substation capacity | The most decisive power factor is usually C |
| Cadastral data is closed in most countries | Land price and zoning are C/D outside the US/EU |
| Pluvial (flash) flooding is absent from global flood datasets | A real blind spot in `clm.flood_riverine` |
| `lnd.contiguous_area` is currently an OSM density heuristic | Tier C; the raster implementation is a roadmap item |
| `clm.extreme_heat_trend` extrapolates observed trend | Tier D and labeled as not a climate projection |
| Cost models are industry-typical ranges, not contractor estimates | Recommendation costs are screening-grade |

None of these are hidden by the scoring: each shows up as a lower tier and therefore a
lower confidence and a wider band.

## Validation

The only evidence the framework works is [dc-validate](../.claude/skills/dc-validate/SKILL.md)
against `data/reference/known_datacenters.yaml` — 12 real sites including three that
were actually rejected, and one paired control (same developer, same county, one
approved and one rejected).

The metric is **discrimination**, not agreement rate: the mean score of built sites
minus the mean score of rejected sites. A model that scores everything 70-80 has a high
agreement rate on positives and is useless.

**Thresholds are never tuned to fit the validation set.** It is a dozen sites; fitting
to it destroys generality. A threshold changes only when the domain argument for it is
wrong, and the reasoning goes in the factor spec.

## Reproducibility

Every measurement is cached by `(factor, source, geohash, params)` with a per-source
TTL. A run is reproducible from its `analysis.json` alone. Re-scoring an old ledger with
a new scoring model is a supported operation and is how model changes should be
evaluated — score the validation set before and after.

# Contributing

The highest-value contributions, in order: **ISO queue parsers**, **cost model
calibration**, and **new adapters** that move an existing factor from Tier C to Tier A/B.

## Adding a factor

Two files, no engine changes.

1. Add an entry to the right `factors/<domain>.yaml`:

```yaml
  - id: dom.your_factor
    name: Human readable name
    question: What question does this answer?
    unit: km
    direction: lower_is_better        # or higher_is_better | categorical
    best_tier: A                      # best tier obtainable, not aspirational
    scale:
      type: piecewise
      points: [[0, 100], [10, 60], [50, 0]]     # x ascending, y in 0-100
    sources: [source_id_from_config]
    adapter: dcgeo.adapters.yourmod:your_fn
    weights: {hyperscale_training: 6, inference_edge: 3, retrofit_colo: 4}
    notes: >
      Why this matters, what the knees in the curve represent, what commonly goes
      wrong when measuring it, and how it differs by jurisdiction.
```

The `notes` field is not decoration — it is what the analyst agents read to know how to
research the factor. A factor with a thin `notes` block will be researched badly.

2. Verify: `uv run dcgeo doctor`. The validator checks weights cover every profile,
scale points ascend, sources are registered, and gate references resolve.

## Adding an adapter

```python
from .base import measured, unknown, http_get, cached, SourceUnavailable

def your_fn(lat: float, lon: float) -> list[Measurement]:
    fid = "dom.your_factor"
    hit, store = cached(fid, SOURCE, lat, lon, params)
    try:
        if hit is None:
            hit = http_get(URL, params=...)
            store(hit)
        return [measured(fid, value, "km", "A", SOURCE, lat=lat, lon=lon,
                         source_url=..., notes="what this means AND its limits")]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "km")]
```

Then register it in `dcgeo/measure.py:DISPATCH`.

**Rules:**
- Never raise past the caller. A dead API returns `unknown`, so one bad endpoint
  cannot abort a 59-factor analysis.
- Never fabricate a fallback value. `unknown` with a reason is always correct;
  a plausible guess is never correct.
- Assign the tier honestly. If you scraped an HTML page, that is C, not B.
- Put the *limits* of the measurement in `notes`, not just the value. The reader needs
  to know what the number does not tell them.

## Adding a data source

Register it in `config/sources.yaml` with tier, auth, coverage, TTL, and license. If
factor specs refer to a specific dataset within it, add an alias rather than a
duplicate source — `gem_retired_plants -> gem_trackers` documents *which part* of a
source a measurement used, which is what you need when a number looks wrong.

## Adding a gate

Declare it in `config/gates.yaml`, implement it in `dcgeo/gates.py` with the `@gate`
decorator. `validate_gate_coverage()` fails CI if config and code disagree. The
`logic:` field in YAML is documentation — the executable truth is the Python.

## Principles

1. **Evidence before score.** The ledger is the product; the score is derived.
2. **Unknown is a valid answer.** Absence of evidence must lower confidence, never
   silently default to a midpoint.
3. **Tier honestly.** Tier inflation is the failure mode that destroys this project.
4. **Every cost is a range with a basis year and a source.**
5. **Don't tune thresholds to fit the validation set.** Change a threshold because the
   domain argument is wrong, and write the reasoning into the factor spec.

## Tests

```bash
uv run pytest
uv run dcgeo doctor          # registry + gate coverage validation
```

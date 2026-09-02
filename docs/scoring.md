# Scoring

Four stages, in order. The order matters: gates before weights is the difference
between a tool that surfaces deal-killers and one that averages them away.

## Stage 1 — Gates

Gates are boolean predicates over measurements, evaluated first, short-circuiting.

| Outcome | Effect |
|---|---|
| `PASS` | Proceed |
| `CONDITIONAL` | Proceed, but the condition becomes a mandatory recommendation with a cost, and the score is capped at `capped_score` until resolved |
| `FAIL` | Verdict is `NO-GO`. Scoring still runs — so you can see *how close* it was and what would unlock it — but the headline verdict does not change |

A gate that fails on **Tier C or D evidence** yields `NO-GO (unverified)` and is flagged
for human verification. See [evidence-tiers.md](evidence-tiers.md).

The eight shipped gates are documented in [gates.md](gates.md), generated from
`config/gates.yaml`.

### Why gates rather than heavy weights

You could express "no power path" as a factor with weight 10. But a weighted average
with one factor at 0 and nine at 85 still produces ~76 — a "viable" site with no
electricity. Weighted averages are inherently unable to represent categorical failure.
Gates are.

## Stage 2 — Normalization

Each factor maps its raw value to 0–100 via a **piecewise-linear** curve defined in its
spec.

Piecewise, not linear, because these relationships have knees. Wet-bulb temperature is
nearly free below 18 °C and expensive above 24 °C; interconnection queue time is
tolerable at 2 years and fatal at 7. Encoding the knee in YAML keeps it visible and
arguable rather than buried in code:

```yaml
scale:
  type: piecewise
  points: [[0, 100], [1, 95], [2, 85], [3, 70], [4, 52], [5, 35], [7, 15], [10, 0]]
```

Values outside the curve clamp to its endpoints. Categorical factors map through an
explicit lookup instead.

## Stage 3 — Profile weighting

The same site is scored separately for each use-case profile, because they weight
factors completely differently:

```
domain_score  = Σ(factor_score × factor_weight) / Σ(factor_weight)     [known factors only]
overall_score = Σ(domain_score × domain_weight) / Σ(domain_weight)     [known domains only]
```

Weights live in the factor specs keyed by profile, so adding a profile is a config
change, not a code change.

**Unknowns are excluded from the mean, never substituted with a midpoint.** They
reduce confidence instead. This is the most important design decision in the scoring
engine — see [evidence-tiers.md](evidence-tiers.md) for why.

`--weight factor_or_domain=multiplier` scales any factor or entire domain at runtime,
which is how a user says "I don't care about water here" without editing the registry.

## Stage 4 — Confidence

```
tier_weight        = {A: 1.00, B: 0.85, C: 0.60, D: 0.35, unknown: 0.00}
confidence         = Σ(weight_i × tier_weight_i) / Σ(weight_i)
band               = ±(1 − confidence) × 22
measured_fraction  = Σ(weight_i where measured) / Σ(weight_i)
```

If `measured_fraction` falls below `min_measured_fraction` (default 0.55), the score is
marked **not publishable** and every surface — CLI, report, agents — must say so rather
than presenting the number as a finding.

## Verdict bands

Applied to the profile score after gates. Gates override.

| Score | Verdict |
|---|---|
| ≥ 75 | strong-candidate |
| ≥ 60 | viable |
| ≥ 45 | conditional |
| ≥ 30 | weak |
| < 30 | poor |
| — | insufficient-data |

## Comparing sites

`dcgeo compare` refuses to rank sites whose confidence bands overlap. Two sites at
`78 ± 9` and `71 ± 3` are not distinguishable by this model, and presenting a false
ordering is worse than presenting none. The tool says which measurement would separate
them instead.

## Re-running with assumptions

```bash
dcgeo rerun run_0031 --assume "pwr.interconnect_queue_time=3" --cooling air_cooled
```

Assumptions are injected as **synthetic Tier-D measurements**, labeled as assumed, and
propagate through gates and scoring. Note the consequence: assuming a value where you
previously had a measurement *lowers* confidence even when it raises the score. That is
correct — you have substituted a guess for a fact.

This is also the mechanism the Recommender uses internally to price interventions: it
does not estimate the score gain, it computes the counterfactual.

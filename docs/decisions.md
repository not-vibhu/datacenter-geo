# From score to decision

A score is not a decision. This page describes the layer that turns one into the
other: `dcgeo/diligence.py`, plus `dcgeo/compare.py` for the multi-site case. Both are
deterministic arithmetic over the evidence ledger — no LLM touches either.

The output is a `DiligenceBrief`, persisted into `runs/<run_id>/analysis.json` under
`diligence` so the decision is auditable from the run directory alone, without
re-running the code that produced it.

```bash
dcgeo brief run_0006                  # human-readable
dcgeo brief run_0006 --json           # the whole object
```

## The question

> Can this site support a profitable data center, and what must be verified next?

Four possible answers:

| Decision | Meaning |
|---|---|
| `NO-GO` | A fatal gate failed on evidence strong enough to act on. Categorical — the remaining factors do not change it. |
| `NOT PROVEN` | Not disqualified, but the evidence does not support a decision either way. |
| `PROCEED WITH CONDITIONS` | Gates satisfied, major conditions outstanding. |
| `PROCEED` | Gates satisfied, and no unmeasured factor can move the verdict across a threshold. |

`NOT PROVEN` is the load-bearing state, and the one most screening work should
produce. It is reached when any of these hold:

- a fatal blocker remains (a failed gate, an undecidable gate, or a dark domain),
- more unmeasured factors than `decision.max_flipping_unknowns_for_proceed` could each
  move the verdict across a threshold on their own,
- the measured fraction is below `aggregation.min_measured_fraction`.

A system that cannot say "not proven" will say something worse instead.

## Profitability is refused separately

Suitability and profitability are different questions, and the score only answers one.
Unless every factor in `decision.profitability_factors` is measured — TCO, retail
power price, large-load tariff, land price, tax incentives — the brief states plainly
that what follows is a suitability screen and not a return, and names the missing
inputs. It does not imply a return from a high score.

## Blockers

Each is one open question standing between the evidence and a decision.

| Kind | Severity | Raised when |
|---|---|---|
| `gate_fail` | fatal | A knockout check failed on Tier A/B evidence |
| `gate_unverified` | fatal | A knockout check failed, but only on Tier C/D evidence |
| `gate_undecidable` | fatal | The factor a knockout check reads is unmeasured |
| `domain_blackout` | fatal / major | A whole domain has no data and left the aggregate |
| `unknown_material` | major / minor | An unmeasured factor carrying material swing |
| `stale` | major | A measured value more than twice its source's refresh window old |
| `weak_evidence` | minor | A Tier-D value doing real work in the score |

Ranked by severity, then by score points at risk.

### Deduplication is the point

A list of 40 blockers is a list nobody reads. Three rules collapse it into a set of
actions:

- A **dark domain absorbs the unknowns inside it.** "Dispatch the regulatory analyst"
  is one action, not seven.
- A **`CONDITIONAL` gate that is only conditional because its input was missing** is
  suppressed in favour of the `gate_undecidable` entry naming the factor — that is the
  one somebody can act on.
- A gate blocker **inherits the swing of the highest-swing factor it reads**, so gate
  blockers and factor blockers sort against each other on the same scale.

### Why a dark domain is its own category

The aggregate is a weighted mean over domains *that have data*. A domain with nothing
measured does not score zero — it drops out of the denominator entirely, and the
headline silently describes a smaller model than the one advertised. That is a
structural hole, not a collection of unknowns, and it gets one loud blocker saying so.

### Every blocker names a counterparty

Routed through `config/verification.yaml`: a per-domain default, overridden per factor
for the ones that decide deals, overridden again by country where the counterparty
differs. A grid capacity question in India goes to the state DISCOM and the State Load
Despatch Centre, not to an ISO queue.

This file is the difference between an unknown and an *actionable* unknown. A system
that reports a gap without naming who can close it has only relabelled the gap.

## Sensitivity

For every weighted factor, the score is recomputed twice — with that factor forced to
0 and to 100, at the tier it would carry if somebody measured it properly. The
difference is its swing.

This runs through `score_profile` itself, via its `counterfactual` parameter, rather
than through a second implementation of the aggregation. A parallel formula would
drift from the scorer it claims to explain. This one cannot.

A factor whose best and worst cases land in different verdict bands **flips the
verdict**: the verdict is not currently determined by evidence, it is determined by
whichever way that factor is assumed to go.

Gate outcomes turn on raw values, not normalized ones, so simulating them would mean
inventing raw values — which the prime directive forbids. Instead, factors a gate
reads are flagged `gate_critical` and reported as blockers: a claim about what is
undecided rather than a fabricated scenario.

## Verification queue

What to find out next, ordered by how much of the decision each answer settles.
Gate-critical items come first regardless of points, because a knockout check that
cannot be evaluated can make everything below it irrelevant.

Each item carries the question from the factor spec, the counterparty, the artifact
that closes it, the typical elapsed time, and the points at risk. `dcgeo brief` and
the static site both render it as a checklist you can hand to somebody.

## Comparison

`dcgeo compare` answers *why* rather than *which*.

- **Separability** — an adjacent pair whose scores differ by less than the mean of
  their bands is not separable, and the ordering is refused rather than printed.
- **Wins and loses** — the factors where a site beats the field, in weighted score
  points contributed. An edge exists only where both sides measured the factor; you
  cannot win on something the other site never measured.
- **Shared blind spots** — factors unmeasured everywhere. These are the questions the
  comparison assumes away equally for every candidate, which is exactly when an
  assumption becomes invisible, and when it is most likely to be wrong in the same
  direction for all of them.

The refusal is the feature. Everything else exists to make the refusal informative
rather than annoying.

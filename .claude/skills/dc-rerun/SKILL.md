---
name: dc-rerun
description: Re-run an existing analysis with new assumptions, modified weights, a different profile, or a changed cooling architecture. Shows exactly which gates flipped and which factors moved. Use for "what would it take to make this work?"
---

# /dc-rerun

Answers "what if" and "what would it take". Creates a child run and diffs it against
the parent — analyses are append-only and never edited in place.

**Usage:**
```
/dc-rerun run_0031 --assume "interconnect_year=2029"
/dc-rerun run_0031 --assume "pwr.onsite_generation_potential=85" --cooling air_cooled
/dc-rerun run_0031 --weight water=0.4 --profile inference_edge
```

## What each flag does

| Flag | Effect |
|---|---|
| `--assume factor_id=value` | Injects a **synthetic Tier-D measurement**, labeled as assumed. Propagates through gates and scoring. |
| `--assume key=value` (non-factor) | Sets a run parameter, e.g. `target_energization_year`, `target_load_mw` |
| `--weight factor_or_domain=multiplier` | Scales a factor's or a whole domain's weight |
| `--cooling` | Changes the cooling architecture; re-evaluates the water gate |
| `--profile` | Scores against a different use case |

## Steps

1. **Confirm what the user is actually asking.** "What if we get power by 2029" is an
   assumption change. "What if we don't care about water" is a weight change. They
   produce very different diffs and users often mean one and say the other.

2. Run it:
   ```bash
   uv run dcgeo rerun run_0031 --assume "pwr.interconnect_queue_time=3" --cooling air_cooled
   ```

3. **Re-run the red team.** New assumptions create new failure modes — an air-cooled
   design that solves the water gate creates a power penalty and a noise problem. Never
   skip this on a re-run.

4. Report the diff: which gates flipped, which factors moved, score delta per profile.

## Rules

- **Assumptions are Tier D and must stay visibly labeled.** A re-run where the user
  assumed away the binding constraint is a hypothetical, not an analysis, and the
  report must say so.
- **Confidence goes down, not up, when you assume.** Substituting an assumption for a
  measurement is a loss of information even when it raises the score. If the score
  rises while confidence falls, say both.
- Chained re-runs accumulate assumptions from the parent. Show the full assumption
  stack, because a run three generations deep can rest on assumptions the user has
  forgotten making.

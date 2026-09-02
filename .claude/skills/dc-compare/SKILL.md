---
name: dc-compare
description: Compare analyzed sites side by side for a given profile, refusing to rank sites whose confidence bands overlap. Use when choosing between candidate locations.
---

# /dc-compare

**Usage:** `/dc-compare run_0031 run_0032 run_0033 --profile hyperscale_training`

## Steps

1. ```bash
   uv run dcgeo compare run_0031 run_0032 run_0033 --profile hyperscale_training
   ```

2. **Check separability first.** The CLI flags pairs whose confidence bands overlap.
   Where they do, report them as tied and explain what measurement would separate
   them. Do not present a false ranking — this is the single most useful thing this
   workflow does, and quietly sorting overlapping scores destroys it.

3. **Compare on the same evidence basis.** A site analyzed at 80% coverage and one at
   30% are not comparable even if their scores differ. Say so and recommend
   completing the thinner analysis first.

4. **Compare domain by domain, not just headline.** Two sites both scoring 68 for
   completely different reasons is the interesting result — one may be fixable and the
   other not.

5. **Compare across profiles where it changes the answer.** If site A wins for
   training and site B for inference, that is the finding, not a tiebreak problem.

## Output shape

```
Profile: hyperscale_training

  run_0033  Abilene TX        strong-candidate   79 ± 6    conf 0.73
  run_0031  Ashburn VA        viable             68 ± 9    conf 0.59
  run_0032  Mt Pleasant WI    conditional        61 ± 14   conf 0.36   capped by gate.water_viable

Not separable: Ashburn (68±9) and Mt Pleasant (61±14) overlap within confidence.
  What would separate them: substation headroom at both (currently Tier C at Ashburn,
  unmeasured at Mt Pleasant).

Where they differ most:
  power        Abilene 84 | Ashburn 55 | Mt Pleasant 71   ← Ashburn's queue is the binding issue
  connectivity Abilene 41 | Ashburn 96 | Mt Pleasant 63   ← irrelevant at this profile weight
  community    Abilene 78 | Ashburn 44 | Mt Pleasant 31
```

## Rules

- Never rank within overlapping bands.
- Never compare a provisional score against a published one without flagging it.
- Report the **decision-relevant** differences, not every domain.

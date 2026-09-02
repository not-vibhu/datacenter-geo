---
name: dc-validate
description: Backtest the scoring model against known data centers and known rejected sites in data/reference/known_datacenters.yaml. Checks that the model discriminates rather than rating everything highly.
---

# /dc-validate

Runs the model against locations whose outcome is already known and reports whether it
would have predicted them. **This is the only evidence that the framework works.**

**Usage:** `/dc-validate` · `/dc-validate --country US` · `/dc-validate --case ashburn_va`

## Why negative controls matter more than positive ones

Any scoring model will rate Ashburn highly — it is surrounded by data centers. The
question is whether it **rejects** sites that were actually rejected. A model that
scores everything 70-80 is useless regardless of how well it ranks the winners.

`data/reference/known_datacenters.yaml` therefore contains three classes:

| Class | Expectation |
|---|---|
| `operating` | Should score viable or better for its actual profile |
| `announced` | Should score viable; disagreement is informative, not necessarily wrong |
| `rejected` | **Should score conditional or worse, or fail a gate** |

## Steps

1. Read `data/reference/known_datacenters.yaml`.

2. For each case, run the analysis at its stated profile:
   ```bash
   uv run dcgeo analyze --at LAT,LON --name "NAME" --profile PROFILE
   ```
   For a full validation, dispatch the domain analysts too — an adapter-only run
   measures ~13/59 factors and will not exercise the regulatory or community gates,
   which are exactly the ones that discriminate.

3. Compare predicted verdict against `expected_verdict`.

4. **Report disagreements as findings, not failures.** A model that scores an
   operating data center as NO-GO is telling you something: either a factor threshold
   is wrong, or the site really does have the problem and was built anyway for reasons
   outside the model (an incumbent's existing campus, a strategic customer, a
   subsidized deal). Both are worth knowing. Investigate before adjusting.

5. **Never tune thresholds to fit the validation set.** That is overfitting to a
   sample of at most a few dozen sites and it destroys the model's generality. If a
   threshold is wrong, change it because the *domain argument* is wrong, and document
   the reasoning in the factor spec.

## Output shape

```
Case                     Class      Expected      Predicted            Agree
ashburn_va               operating  viable+       viable (68±9)        yes
abilene_tx               announced  viable+       strong (79±6)        yes
ulanqab_nmg              operating  viable+       viable (71±11)       yes
jamnagar_gj              announced  viable+       conditional (58±13)  no  ← investigate
<negative control>       rejected   conditional-  NO-GO (moratorium)   yes

Agreement: 4/5. Discrimination: positives mean 72, negatives mean 31 — separated.
```

The **discrimination** line is the one that matters. If positives and negatives have
similar means, the model is not working, no matter how high the agreement rate looks.

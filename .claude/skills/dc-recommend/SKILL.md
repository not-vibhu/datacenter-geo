---
name: dc-recommend
description: Generate ranked interventions with cost ranges, timelines, and responsible actors for an analyzed site — what to do to make this location more suitable. Ranked by score points per dollar.
---

# /dc-recommend

**Usage:** `/dc-recommend run_0031` · `/dc-recommend run_0031 --budget 50M`

## Steps

1. Load the scored run. If the measured fraction is below the floor, say so first —
   recommendations built on 25% coverage are guesses about guesses.

2. Dispatch **recommender**.

3. For each proposed intervention, **verify the gain by actually re-running**:
   ```bash
   uv run dcgeo rerun run_0031 --assume "wtr.reclaimed_availability=3.0"
   ```
   Do not estimate the score gain in your head. The whole point of a deterministic
   scoring engine is that you can measure the counterfactual.

4. Rank by leverage — score points per $10M — and present the table.

5. If `--budget` was given, solve for the best combination within it and state what
   verdict band that buys.

## Output shape

```
Current: conditional (61 ± 12), capped by gate.water_viable

Worth doing:
  1. Reclaimed water pipeline, 4.2 km    $9-16M    14-20 mo   +13 pts   leverage 1.04   developer
  2. Acoustic setback + barrier          $2-4M      6-9 mo    +5 pts    leverage 1.67   developer
  3. Substation upgrade cost-share       $22-38M   30-42 mo   +9 pts    leverage 0.30   utility + developer

Not fixable here:
  - Seismic PGA 0.34 g — accept the ~6-9% structural premium or reject the site
  - Latency to Chicago 41 ms — physics; only relevant if you re-profile to inference

To reach 'viable' (60+): items 1-2, $11-20M, ~20 months.
```

## Rules

- **Every cost is a range with a basis year and a source.** A point estimate for a
  transmission build is a fiction.
- **Name the actor.** An intervention requiring utility or county agreement is not a
  developer decision and carries different risk. "Secure a large-load tariff" is a
  negotiation with a counterparty who may refuse.
- **Say what is unfixable.** A recommendations list that implies everything is
  solvable is dishonest. Some sites are wrong and should be rejected.
- Do not recommend against low-weight factors just to fill the table.

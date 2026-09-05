# datacenter-geo

**An evidence-backed diligence system for AI data center siting.**

Give it a coordinate, a parcel, a county, or a whole region. It runs a multi-agent
analysis across 59 decision factors — power, water, climate, land, connectivity,
regulation, community, supply chain — and answers one question:

> **Can this site support a profitable data center, and what must be verified next?**

The answer is a decision, not a score: `PROCEED`, `PROCEED WITH CONDITIONS`, `NO-GO`,
or — most often, and most usefully — `NOT PROVEN`, with the specific open questions
that are preventing a decision, each priced in score points and addressed to the
counterparty who can close it.

```bash
dcgeo analyze --at "39.0437,-77.4875" --radius 25 --profile hyperscale_training
dcgeo brief   run_0031                    # the decision, blockers, and what to verify next
dcgeo compare run_0006 run_0008           # why each site wins and loses, not just a rank
dcgeo scan --bbox 31.5,-102.5,33.0,-100.0
dcgeo rerun run_0031 --assume "grid_upgrade_2029=true" --weight water=0.5
```

Or, inside Claude Code:

```
/dc-analyze 39.0437,-77.4875
/dc-scan "Telangana, India" --min-mw 500
/dc-recommend run_0031
```

## India map workspace

The web app now starts in **Bhopal**, with drill-down between Bhopal, Madhya Pradesh
and India. Explore the sourced facility directory, switch infrastructure layers,
inspect satellite imagery, and draw or edit exact site boundaries. Saved boundaries
stay in this browser and export as GeoJSON for the analysis engine.

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
# Open http://127.0.0.1:8765
uv run dcgeo analyze --boundary boundary.geojson --profile hyperscale_training
```

The India heatmap shows facility density; the Bhopal pilot also shows mapped
substation proximity. Both are exploration signals. **A national investment
suitability surface is not yet implemented.** Current adapters still measure around
an interior reference point even when an exact boundary is supplied.

The app uses committed, attributed source snapshots and keeps its map and boundary
tools usable if a snapshot fails to load. No paid API keys are required for the pilot.
Existing scoring reports remain accessible from **Analysis reports**.
See [the atlas workflow, data contracts and expansion plan](docs/india-atlas.md).

## Why this exists

Site selection for AI infrastructure is currently done with spreadsheets, broker
relationships, and 6-month consulting engagements. The data needed to make the
decision is public — it is just scattered across ISO interconnection queues, county
GIS portals, PUC dockets, satellite rasters, and local news archives, in a hundred
incompatible formats.

This repo makes that analysis reproducible, auditable, and fast enough to run on a
thousand candidate sites instead of three.

## The honest part

Roughly 15 of the 59 factors can be measured precisely from open APIs — climate,
terrain, flood, seismic, fiber routes, grid carbon. The factors that actually decide
deals cannot: interconnection queue position, whether a utility will *really* serve a
500 MW load, land price, whether the county board will approve it.

So every metric in this system carries an **evidence tier**:

| Tier | Meaning | Example |
|------|---------|---------|
| **A** | Machine API, reproducible, versioned | Wet-bulb hours from ERA5 |
| **B** | Bulk file or structured scrape | ISO interconnection queue XLSX |
| **C** | Agent web research with citations | County board sentiment on prior applications |
| **D** | Modeled, analogized, or estimated | Land price from regional comparables |

A site scoring 82 on Tier-A/B evidence is a completely different asset from one
scoring 82 on Tier-C/D evidence. The system never hides that difference: every score
ships with a confidence band and an evidence ledger.

Tier answers *how was this obtained*. It does not answer *is it still true*, so every
datapoint also carries its retrieval timestamp, and is discounted against its source's
declared refresh window. A Tier-A number three years past its TTL reports lower
confidence than the same number measured yesterday, and widens the ± band accordingly.

**This tool does not replace due diligence.** It tells you which twenty sites out of
two thousand deserve due diligence, and what to ask when you get there — which is what
the verification queue is: a ranked, addressed list of the questions that would settle
the decision.

## How it works

```
                    ┌──────────────┐
   region or  ─────▶│  PROSPECTOR  │  generates candidate sites from first principles
   coordinate       └──────┬───────┘  (power corridors ∩ land ∩ fiber ∩ climate)
                           │
                    ┌──────▼───────┐
                    │PARCEL RESOLVER│  coordinate → AOI polygon, tiles, admin context
                    └──────┬───────┘
                           │
        ┌──────────┬───────┼───────┬──────────┬──────────┐
        ▼          ▼       ▼       ▼          ▼          ▼
     POWER      WATER   CLIMATE   LAND    CONNECT.   REGULATORY    ← 8 domain analysts
    ANALYST    ANALYST  ANALYST  ANALYST  ANALYST     ANALYST        run in parallel
        │          │       │       │          │          │
        └──────────┴───────┼───────┴──────────┴──────────┘
                           │  evidence ledger (every claim + source + tier)
                    ┌──────▼───────┐
                    │   RED TEAM   │  adversarial: tries to kill the site
                    └──────┬───────┘
                    ┌──────▼───────┐
                    │    SCORER    │  gates → profile weights → confidence bands
                    └──────┬───────┘
                    ┌──────▼───────┐
                    │  RECOMMENDER │  gap → intervention → cost estimate
                    └──────┬───────┘
                           ▼
              site_analysis.json + report.md + site.geojson
```

Read [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## Scoring is gated, not averaged

A weighted average will happily tell you a site is "78/100" when it has no path to
power before 2032. That is worse than useless — it is confidently wrong.

So scoring runs in three stages:

1. **Gates** — hard knockouts evaluated first. No credible path to target MW by
   target year, or a 500-year floodplain, or an active moratorium → `NO-GO`,
   full stop, regardless of every other factor.
2. **Profile scores** — the same site is scored separately for
   `hyperscale_training`, `inference_edge`, and `retrofit_colo`. These weight water,
   latency, land size and power density completely differently. A West Texas mega-site
   that's brilliant for training is useless for edge inference.
3. **Confidence** — derived from the evidence tiers actually achieved, not the tiers
   theoretically available, and discounted for age. Reported as a band, not a point.

A gate whose input is unmeasured does not quietly pass. It is reported as
**undecidable**, which is a different and more honest state than *satisfied*: the
knockout check ran against nothing, so its result is not evidence. Likewise a domain
with no measurements at all drops out of the weighted mean entirely — the system says
so rather than letting the headline quietly describe a smaller model than advertised.

## From score to decision

Scoring is the middle of the pipeline, not the end. Four things turn it into something
somebody can act on, all of them deterministic and all in `dcgeo/diligence.py`:

- **Decision blockers.** Every open question standing between the evidence and a
  decision — a failed gate, an undecidable gate, a dark domain, a material unknown,
  a stale or modeled number doing real work in the score. Each is ranked by severity
  then by score points at risk, and each names the counterparty who can close it and
  the artifact that closes it (`config/verification.yaml`).
- **Sensitivity.** Every factor is re-scored at its best and worst plausible
  resolution, one at a time, *through the real scorer* — so the sensitivity can never
  disagree with the score it is explaining. Anything that moves the result across a
  verdict threshold on its own is a factor the evidence has not yet decided.
- **Verification queue.** What to find out next, ordered by how much of the decision
  each answer settles. Gate-critical items come first regardless of points, because a
  knockout check that cannot be evaluated can make everything below it irrelevant.
- **Profitability, refused by default.** Suitability and profitability are different
  questions. Unless the tariff, land price, incentive and TCO inputs are measured, the
  brief states plainly that the score is a suitability screen and not a return.

```bash
dcgeo brief run_0006                 # decision, blockers, swing factors, queue
dcgeo brief run_0006 --json          # the same, machine-readable
```

## Comparison explains itself

A ranked list of scores is the least useful thing this system can output.
`dcgeo compare` reports **why each site wins and loses** — the factors where it beats
the field, in weighted score points contributed — and refuses to present an ordering
when the confidence bands overlap:

```
Not separable: 1 adjacent pair overlap within their confidence bands
(run_0006 / run_0008). The ordering is not supported by the evidence —
compare them on the win/lose reasons below, not on the score.

Hanover Ashland VA (APPROVED 2024)
  + Organized opposition risk          +80 vs field  +1.77 pts  C
  + Zoning and entitlement status      +27 vs field  +0.60 pts  C
  - Transmission line proximity         -4 vs field  -0.10 pts  A
```

It also reports **shared blind spots** — factors unmeasured for every candidate, which
are the questions the comparison silently assumes away equally, and therefore the ones
most likely to be wrong in the same direction for all of them.

## Install

```bash
uv sync
cp .env.example .env    # optional: all core sources work with zero keys
uv run dcgeo doctor     # checks which data sources are reachable
```

Every Tier-A/B source used by default is free and keyless or free-with-registration.
Paid adapters (Earth Engine, Planet, S&P Global, CoStar) have written interfaces in
`dcgeo/adapters/paid/` and are skipped cleanly when no key is present.

## Repo map

| Path | What's in it |
|------|--------------|
| `.claude/agents/` | The 14 subagent definitions |
| `.claude/skills/` | Slash-command workflows (`/dc-analyze`, `/dc-scan`, …) |
| `factors/` | 59 factor specs — formula, thresholds, sources, gate, weights |
| `config/` | Profiles, gates, source registry, verification routing |
| `dcgeo/` | Python: scoring engine, diligence layer, evidence ledger, adapters |
| `site/` | India map workspace, boundary editor and evidence reports; attributed basemap tiles |
| `data/reference/` | Validation set: known data centers + negative controls |
| `docs/` | Methodology, evidence tiers, scoring math, source catalog |
| `crons/` | Scheduled global sweep specs |

## Status

Early. The architecture and factor framework are complete; adapter coverage is
partial and marked per-factor in `dcgeo doctor`. See [ROADMAP.md](ROADMAP.md).

Licensed MIT. Contributions welcome — a new factor is one YAML entry and one
adapter function; see [CONTRIBUTING.md](CONTRIBUTING.md).

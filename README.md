# datacenter-geo

**An agent harness for evaluating whether a place on Earth can host an AI data center.**

Give it a coordinate, a parcel, a county, or a whole region. It runs a multi-agent
analysis across 59 decision factors — power, water, climate, land, connectivity,
regulation, community, supply chain — and returns a gated, profile-specific score
with every number traced back to its source.

```bash
dcgeo analyze --at "39.0437,-77.4875" --radius 25 --profile hyperscale_training
dcgeo scan --region "West Texas" --min-mw 300 --top 20
dcgeo rerun run_0031 --assume "grid_upgrade_2029=true" --weight water=0.5
```

Or, inside Claude Code:

```
/dc-analyze 39.0437,-77.4875
/dc-scan "Telangana, India" --min-mw 500
/dc-recommend run_0031
```

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

**This tool does not replace due diligence.** It tells you which twenty sites out of
two thousand deserve due diligence, and what to ask when you get there.

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
   theoretically available. Reported as a band, not a point.

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
| `config/` | Use-case profiles, gate definitions, data source registry |
| `dcgeo/` | Python: scoring engine, evidence ledger, source adapters |
| `data/reference/` | Validation set: known data centers + negative controls |
| `docs/` | Methodology, evidence tiers, scoring math, source catalog |
| `crons/` | Scheduled global sweep specs |

## Status

Early. The architecture and factor framework are complete; adapter coverage is
partial and marked per-factor in `dcgeo doctor`. See [ROADMAP.md](ROADMAP.md).

Licensed Apache-2.0. Contributions welcome — a new factor is one YAML entry and one
adapter function; see [CONTRIBUTING.md](CONTRIBUTING.md).

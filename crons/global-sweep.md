# Scheduled global sweep

Continuous worldwide discovery. Two jobs run on different cadences, because they have
different value profiles.

## Job 1 — Frontier advance (weekly)

Scans the next batch of unexamined tiles and promotes candidates.

```
Schedule:  0 3 * * 1          (Mondays 03:00 local)
Command:   /dc-sweep --band <current> --tiles 200
Budget:    200 tiles, ~40 min, roughly 600 API calls
```

The world is too large to scan uniformly. Priority bands scan where data centers can
actually be built, in order:

| Band | Region | Why here first |
|---|---|---|
| 1 | US: ERCOT, PJM fringe, MISO West, Southeast non-ISO | Largest load growth, best data, fastest queues |
| 2 | India: Maharashtra, Tamil Nadu, Telangana, Gujarat, UP, Odisha | Active state DC policies, growing demand |
| 3 | China: 东数西算 hub clusters | Designated, subsidized, power-rich |
| 4 | Europe: Nordics, Iberia, Ireland fringe, Poland | Cheap clean power, cool climate, cheap cooling |
| 5 | Gulf, SE Asia, Brazil, Canada, Australia | Emerging; data quality varies widely |

State lives in `runs/sweep_state.json` so each run advances rather than repeating.

## Job 2 — Staleness refresh (daily)

**The more valuable half.** A site analysis is a perishable good. This job re-checks
analyzed sites for state changes that invalidate prior conclusions.

```
Schedule:  0 6 * * *          (daily 06:00)
Command:   /dc-sweep --refresh-only
Budget:    ~50 sites, ~15 min
```

Refresh triggers, in priority order by how fast they move:

| Trigger | TTL | Why it matters |
|---|---|---|
| Export control rule change | 7 d | Can flip `gate.compute_legally_deployable` overnight |
| ISO queue posting | 14 d | A competitor filing near your site consumes the headroom you were counting on |
| Moratorium enacted or expired | 14 d | Flips `gate.no_active_moratorium` in either direction |
| PUC docket activity | 30 d | Large-load tariffs and cost allocation |
| Drought declaration | 30 d | Can flip `gate.water_viable` |
| Transmission project approval | 90 d | Can shorten a power path by years |
| Incentive statute change | 90 d | Sunsets and legislative sessions |

A site that was NO-GO last quarter because of a moratorium may be viable today. That
is exactly the kind of change this system should catch and a human reviewing a static
spreadsheet never would.

## Job 3 — Leaderboard rebuild (weekly)

```
Schedule:  0 5 * * 1
Command:   uv run dcgeo compare $(ls -d runs/run_* ) --profile hyperscale_training
```

Rebuilds `runs/leaderboard.json`. Respects confidence bands — sites within overlapping
bands are grouped as tied rather than falsely ordered.

## Setting these up

In Claude Code, use the `/schedule` skill or the scheduled-tasks tooling:

```
/schedule weekly Monday 3am — run /dc-sweep --band 1 --tiles 200
/schedule daily 6am — run /dc-sweep --refresh-only
```

Or with plain cron against the CLI for the deterministic parts:

```cron
0 3 * * 1  cd /path/to/datacenter-geo && uv run dcgeo scan --bbox "$(cat crons/next_bbox)" --step 25 --max-tiles 200
```

## Operating rules

- **Bounded cost per run, always.** An unbounded sweep exhausts API rate limits and
  produces nothing. Set the tile budget and respect it.
- **Rate limits are the real constraint at scale.** The public Overpass and Nominatim
  endpoints will block bulk use. Self-hosting Overpass and using a paid geocoder is a
  prerequisite for running sweeps at any serious volume — this is the single biggest
  practical obstacle to scaling this system, and it should be solved before band 1 is
  exhausted.
- **Never auto-publish a promoted site as a finding.** Sweeps generate leads. Leads
  need the full `/dc-analyze` workflow, red team included, before anyone acts.
- **Report changes, not status.** Nobody reads a daily "still scanning" message. If
  nothing changed, one line.

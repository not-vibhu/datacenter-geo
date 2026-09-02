---
name: dc-sweep
description: Advance the continuous global discovery frontier — scan the next batch of world tiles, promote candidates, and re-check previously analyzed sites for state changes that invalidate prior conclusions. Designed to run on a schedule.
---

# /dc-sweep

The scheduled job behind continuous worldwide discovery. Designed to be run by cron
(see `crons/global-sweep.md`) but usable manually.

**Usage:** `/dc-sweep` · `/dc-sweep --band 1 --tiles 200` · `/dc-sweep --refresh-only`

## Two jobs, both necessary

### 1. Advance the frontier
Scan the next batch of unexamined tiles and promote anything above threshold.

Priority bands, in order — the world is too large to scan uniformly, so scan where
data centers can actually be built:

| Band | Region | Rationale |
|---|---|---|
| 1 | US ERCOT, PJM fringe, MISO West, Southeast | Largest load growth, fastest queues, best data |
| 2 | India — Maharashtra, TN, Telangana, Gujarat, UP, Odisha | Active state DC policies, growing demand |
| 3 | China — 东数西算 hub clusters | Designated, subsidized, power-rich |
| 4 | Nordics, Iberia, Ireland fringe, Poland | Cheap clean power, cool climate |
| 5 | Gulf, SE Asia, Brazil, Canada, Australia | Emerging, variable data quality |

Track the frontier in `runs/sweep_state.json` so each run advances rather than
repeating.

### 2. Refresh what you already know — this is the more valuable half
A site analysis is a **perishable good**. Re-check analyzed sites for state changes
that invalidate prior conclusions:

- New interconnection queue postings near the site (competitors consuming headroom)
- Moratorium enactments or expirations
- Drought declarations or basin status changes
- Transmission project approvals that shorten a power path
- Incentive statute changes or sunsets
- **Export control rule changes** — 7-day TTL, the fastest-moving input in the system

Any of these can flip a gate. A site that was NO-GO last quarter because of a
moratorium may be viable today, and that is exactly the kind of thing this system
should catch and a human never would.

## Steps

1. Read `runs/sweep_state.json` for the current frontier position.
2. Run the coarse pass over the next tile batch: `uv run dcgeo scan --bbox ... --step 25`.
3. Cheap-kill survivors on the six highest-kill-rate factors.
4. Promote anything above threshold to `/dc-analyze`.
5. Re-check stale analyses: any run whose measurements exceed their source TTL.
6. Append to `runs/leaderboard.json`, update sweep state.
7. Report **only what changed.** A sweep that found nothing should say so in one line.

## Rules

- **Bounded cost per run.** Set a tile budget and respect it. An unbounded sweep will
  exhaust API rate limits and produce nothing.
- **Respect rate limits.** The public Overpass and Nominatim endpoints will block bulk
  use — self-host or use a paid geocoder before scaling this up. This is the single
  biggest practical obstacle to running sweeps at scale.
- **Never auto-publish a promoted site as a finding.** Sweeps generate leads. Leads
  need the full workflow, including the red team, before anyone acts on them.
- Report changes, not status. Nobody reads a daily "still scanning" message.

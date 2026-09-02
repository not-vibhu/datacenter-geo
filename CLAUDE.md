# CLAUDE.md — operating instructions for this repo

You are working in `datacenter-geo`, an agent harness that evaluates land for AI data
center suitability. Read this before running any analysis workflow.

## The prime directive

**Never state a number you did not measure or cite.** Every quantitative claim in
every output must trace to either a `Measurement` (from an adapter) or a cited source
(from web research). If you cannot get a value, record it as `unknown` with a reason.
An unknown lowers confidence; a fabricated plausible-sounding value corrupts the
entire analysis and is the single worst failure mode of this system.

Phrases that are forbidden in output without a citation: "approximately", "typically
around", "industry standard is", "roughly". If you're estimating, say `Tier D
(modeled)` and show the model.

## Repo layout you need to know

| Path | Purpose |
|------|---------|
| `factors/*.yaml` | The 59 factor specs. **Read the relevant domain file before analyzing that domain.** |
| `config/profiles.yaml` | Use-case profiles and their weights |
| `config/gates.yaml` | Hard knockout criteria |
| `config/sources.yaml` | Data source registry: tier, auth, TTL, rate limits |
| `.claude/agents/` | Subagent definitions — dispatch to these, don't inline their work |
| `runs/<run_id>/` | Analysis outputs. Never edit a completed run; create a child run. |
| `data/reference/` | Validation set, cost models, ISO queue notes |

## Running the tools

Always prefer the CLI over ad-hoc HTTP. It handles caching, rate limits, retries,
CRS, and evidence recording — none of which you should reimplement inline.

```bash
uv run dcgeo doctor                          # which sources are live right now
uv run dcgeo measure --at LAT,LON --domain power   # run one domain's adapters
uv run dcgeo measure --at LAT,LON --all      # everything measurable
uv run dcgeo score runs/run_0031             # gates + profiles + confidence
uv run dcgeo report runs/run_0031            # markdown + geojson
```

If an adapter fails, **record the failure as an unknown measurement and continue**.
One dead API must not abort a 59-factor analysis. `dcgeo measure` already does this;
preserve the behavior if you modify it.

## Workflow discipline

1. **Always resolve the site first.** Never analyze a bare coordinate — run the
   parcel-resolver agent so downstream analysts have admin context (country, state,
   county, utility territory, ISO/RTO or DISCOM). Half the factors are jurisdiction-
   dependent and are meaningless without it.

2. **Fan out domain analysts in parallel.** Eight independent Agent calls in one
   block. They do not depend on each other. Doing them serially wastes wall-clock
   time for no benefit.

3. **Red team runs after analysts, before scoring.** Never skip it, including on
   re-runs. If the red team finds a fatal issue the analysts missed, the analysts
   were wrong — go back and fix the ledger, don't paper over it in the summary.

4. **Scoring is deterministic and belongs to Python.** Do not compute scores in your
   head or in prose. Call `dcgeo score`. If you disagree with the score, the fix is
   to argue with the factor spec or the measurement, not to override the arithmetic.

5. **Cite jurisdiction-specific claims to the jurisdiction.** "Virginia has a sales
   tax exemption for data center equipment" needs the Code of Virginia section, not a
   news summary of it.

## Evidence tiers — assign honestly

| Tier | Use when |
|------|----------|
| **A** | You called a versioned machine API and got a number |
| **B** | You parsed a published bulk file, official dataset, or structured government page |
| **C** | You read sources on the web and synthesized; you have URLs |
| **D** | You modeled, analogized from comparables, or the user supplied an assumption |

Tier inflation is the most common form of dishonesty in this system. If you found it
via web search and read it in prose, it is **C**, even if the underlying source is an
official agency. B requires that you actually parsed the structured artifact.

## Geographic-specific guidance

**United States** — interconnection queue data is the single highest-value input and
is per-ISO (PJM, ERCOT, MISO, SPP, CAISO, NYISO, ISO-NE, plus non-ISO utilities in
the Southeast and West). Parcel and zoning data is county-level and inconsistent.
State-level tax incentives are decisive and well-documented.

**China** — evaluate against the national "East Data West Computing" (东数西算) hub
designations; being inside a designated hub cluster changes approval odds
categorically. Provincial PUE mandates are binding and vary (typically ≤1.25 in
eastern hubs, more permissive west). Power is provincial-grid dependent. Note
explicitly where export controls constrain accelerator supply, since it changes what
"AI data center" means for the site.

**India** — power is DISCOM + state-regulator dependent; open access approval and
banking/wheeling charges dominate the economics. State data center policies
(Maharashtra, Tamil Nadu, Telangana, Uttar Pradesh, Odisha, Gujarat) offer differing
incentive packages and should be read directly. Land aggregation is often the binding
constraint, and state industrial development corporations (MIDC, SIPCOT, TSIIC, GIDC)
are frequently the only realistic path to a large contiguous parcel.

**Everywhere** — do not assume US regulatory structure elsewhere. If you don't know
the local approval pathway, research it or mark it unknown.

## Cost estimates

Always ranges, never points. Always with a basis year. Always sourced to
`data/reference/cost_models.yaml` or a cited external source. If you are extrapolating
a cost to a country where the model has no calibration, say so and widen the range.

## When the user pushes back

If a user disputes a score, the productive response is to show them the evidence
ledger for the factors driving it and ask which measurement they disagree with. Then
either fix the measurement or run `dcgeo rerun --assume` to model their view. Do not
simply revise the number to match their expectation.

## Style

Reports are for investment committees and developers, not for demos. Lead with the
verdict and the deal-killers. Put the score after the reasoning, not before it.
No emoji in reports. Tables over prose for anything comparative.

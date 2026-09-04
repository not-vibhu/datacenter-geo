# Evidence tiers

The most important idea in this system. A score is only as good as the evidence under
it, and the single most common failure of site-selection tools is presenting a
confident number built on guesses.

## The tiers

| Tier | Definition | Weight | Example |
|---|---|---|---|
| **A** | You called a versioned machine API and got a number | 1.00 | Wet-bulb hours from ERA5 via Open-Meteo |
| **B** | You parsed a published bulk file, official dataset, or structured government page | 0.85 | PJM interconnection queue XLSX |
| **C** | You read sources on the web and synthesized; you have URLs | 0.60 | County board sentiment from meeting minutes |
| **D** | You modeled, analogized from comparables, or the user assumed it | 0.35 | Land price from regional comparables |
| **unknown** | Not measured, with a recorded reason | 0.00 | Substation headroom, utility would not disclose |

## Why "unknown" is a first-class value

Most scoring systems treat a missing input as a midpoint, or drop it from the average.
Both are wrong, and the second is worse because it is invisible.

Consider two sites. Site A has measured substation headroom of 400 MVA. Site B's
utility will not disclose it. If the missing value is dropped from the average, Site B
scores *higher* than Site A on everything else it happens to be good at — and the
single most likely cause of its failure has silently vanished from the analysis.

So in this system:
- An unknown is recorded as a `Measurement` with `value=None` and a **reason**
- It is excluded from the domain mean, so it cannot fake a score
- It **lowers confidence**, so the band widens and the score becomes less claimable
- Below the configured coverage floor (default 55%), the system **refuses to publish
  a headline score at all**

That refusal is a feature. A tool that always produces a number will always be used to
produce a number.

## Confidence and bands

```
confidence = Σ(weight_i × tier_weight_i) / Σ(weight_i)
band       = ±(1 − confidence) × 22
```

Reported as `78 ± 9 (confidence 0.61)`.

The band is not decoration. `78 ± 9` and `71 ± 3` are **not rankable** — the compare
workflow says so explicitly rather than sorting them. Presenting a false ordering
between two sites you cannot actually distinguish is worse than presenting no ordering.

## Tier inflation is the failure mode that matters

If an analyst records a web-researched claim as Tier B because the underlying publisher
is an official agency, confidence rises without evidence rising. Do that a dozen times
and the system produces a confident number with nothing behind it — exactly the
artifact it exists to prevent.

The rule: **B requires that you actually parsed the structured artifact.** A news
article summarizing a statute is C. A PDF you read in prose is C. The statute text
itself, parsed, is B. An API returning JSON is A.

The `evidence-librarian` agent audits for this. Run it before anything is published
externally or acted on.

## Gates and low-confidence evidence

Gates are categorical and short-circuit — but a gate that FAILS on Tier C or D
evidence produces `NO-GO (unverified)` rather than `NO-GO`, and is flagged for human
verification.

We do not kill sites on the strength of a news article. A moratorium reported in local
press might be proposed rather than enacted, might already have expired, might exempt
by-right industrial zones, or might cap by megawatt rather than banning outright. The
system surfaces it and asks a human to check.

## Practical tier ceilings by domain

Be realistic about what is achievable. Some domains simply cannot reach Tier A:

| Domain | Typical achievable | Why |
|---|---|---|
| climate | A | Global versioned rasters and reanalysis exist |
| connectivity | A for IXPs, C/D for routes | Carriers do not publish terrestrial routes |
| power | A for proximity, B for queues, C for headroom | Utilities do not publish capacity |
| land | A for slope, C/D for price and zoning | Cadastral data is closed in most countries |
| water | A for wet-bulb and basin stress, C for rights | Rights are jurisdiction-specific documents |
| regulatory | B/C | Statutes are readable, timelines are not published |
| community | C | Built from news, minutes, and petitions by nature |
| economics | C/D | Market intelligence is commercial |

A `power` analysis at overall Tier C is not a failure — it may be the ceiling for that
jurisdiction. What matters is that the report says so.

## Tier is not freshness

Tier answers *how was this obtained*. It does not answer *is it still true*.

A Tier-A interconnection queue reading from three years ago is stale in a way the tier
alone cannot express, and a system that treats it as current will confidently
recommend a site on a number that has since moved. So every measurement is also judged
against its source's declared `ttl_days` in `config/sources.yaml`:

| Freshness | Age | Multiplier |
|---|---|---|
| `fresh` | within the refresh window | 1.00 |
| `aging` | past it, under twice it | 0.85 |
| `stale` | more than twice the window | 0.55 |
| `undated` | no retrieval timestamp, or an unregistered source | 0.70 |

The weight a datapoint actually carries is `tier_weight × freshness_multiplier`, and
that is what feeds confidence — so a ledger of stale Tier-A numbers reports lower
confidence, and a wider band, than one measured yesterday. Staleness costs what a
weaker tier costs, because in practice it is the same problem.

Multipliers live in `config/profiles.yaml` under `freshness:` so they are arguable
rather than buried. A measurement whose value is unknown carries zero regardless.

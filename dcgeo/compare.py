"""Site comparison that explains itself.

A ranked list of scores is the least useful thing this system can output. Two
sites at 78 and 74 are not "one better than the other" — they are two different
bets, and the interesting question is always *what does each one buy you and
what does it cost you*.

So a comparison here produces three things and refuses to produce a fourth:

  * **separability** — whether the evidence supports ranking these sites at all.
    Overlapping ± bands mean the ordering is noise, and we say so instead of
    printing it.
  * **why each site wins** — the factors where it beats the field by more than
    the noise, in weighted score points contributed.
  * **why each site loses** — the same, in the other direction, plus the
    blockers unique to it.
  * and **shared blind spots** — factors unmeasured everywhere, which are the
    questions the comparison silently assumes away for all candidates equally.

The refusal is the point. Everything else in the file exists to make the refusal
informative rather than annoying.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import pairwise
from typing import Any

from .diligence import build_brief
from .models import Analysis
from .registry import load_factors


@dataclass
class Edge:
    """One factor's contribution to the gap between a site and the field."""

    factor_id: str
    name: str
    domain: str
    weight: float
    site_normalized: float | None
    field_normalized: float | None      # mean across the other sites that measured it
    delta: float                        # site - field, in normalized points
    contribution: float                 # delta * weight / total_weight, in score points
    site_tier: str
    comparable: bool                    # both sides measured it

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SiteComparison:
    run_id: str
    name: str
    decision: str
    score: float | None
    band: float
    confidence: float
    measured_fraction: float
    wins: list[Edge] = field(default_factory=list)
    loses: list[Edge] = field(default_factory=list)
    unique_blockers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["wins"] = [e.to_dict() for e in self.wins]
        d["loses"] = [e.to_dict() for e in self.loses]
        return d


@dataclass
class Comparison:
    profile: str
    sites: list[SiteComparison]
    separable: bool
    separability_note: str
    overlapping_pairs: list[tuple[str, str]] = field(default_factory=list)
    shared_blind_spots: list[dict[str, Any]] = field(default_factory=list)
    comparable_fraction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sites"] = [s.to_dict() for s in self.sites]
        return d


def compare(analyses: list[Analysis], profile: str, top_n: int = 5) -> Comparison:
    factors = load_factors()
    briefs = {a.run_id: build_brief(a, profile) for a in analyses}
    scores = {a.run_id: a.profiles.get(profile) for a in analyses}

    # Normalized value per factor per site, and the field mean excluding self.
    per_site: dict[str, dict[str, Any]] = {}
    weights: dict[str, float] = {}
    for a in analyses:
        ps = scores[a.run_id]
        if not ps:
            continue
        per_site[a.run_id] = {
            fs.factor_id: fs for fs in ps.factor_scores if fs.normalized is not None
        }
        for fs in ps.factor_scores:
            weights[fs.factor_id] = fs.weight

    total_w = sum(weights.values()) or 1.0

    out_sites: list[SiteComparison] = []
    for a in analyses:
        ps, brief = scores[a.run_id], briefs[a.run_id]
        if not ps:
            continue
        mine = per_site.get(a.run_id, {})
        edges: list[Edge] = []
        for fid, fs in mine.items():
            others = [
                per_site[r][fid].normalized
                for r in per_site
                if r != a.run_id and fid in per_site[r]
            ]
            if not others:
                continue
            field_mean = sum(others) / len(others)
            delta = fs.normalized - field_mean
            edges.append(Edge(
                factor_id=fid,
                name=factors[fid]["name"],
                domain=fs.domain,
                weight=fs.weight,
                site_normalized=fs.normalized,
                field_normalized=round(field_mean, 2),
                delta=round(delta, 2),
                contribution=round(delta * fs.weight / total_w, 3),
                site_tier=fs.tier,
                comparable=True,
            ))
        edges.sort(key=lambda e: -e.contribution)
        out_sites.append(SiteComparison(
            run_id=a.run_id,
            name=a.site.name,
            decision=brief.decision,
            score=ps.score,
            band=ps.band,
            confidence=ps.confidence,
            measured_fraction=ps.measured_fraction,
            wins=[e for e in edges if e.delta > 0][:top_n],
            loses=[e for e in edges if e.delta < 0][-top_n:][::-1],
            unique_blockers=[
                b.to_dict() for b in brief.blockers
                if b.severity in ("fatal", "major")
                and not any(
                    b.blocker_id in {x.blocker_id for x in briefs[r].blockers}
                    for r in briefs if r != a.run_id
                )
            ][:4],
        ))

    # Separability: any adjacent pair whose bands overlap makes the ordering unsafe.
    ranked = sorted(
        [s for s in out_sites if s.score is not None], key=lambda s: -s.score
    )
    overlapping: list[tuple[str, str]] = []
    for x, y in pairwise(ranked):
        if abs(x.score - y.score) < (x.band + y.band) / 2:
            overlapping.append((x.run_id, y.run_id))

    separable = not overlapping and len(ranked) > 1
    if len(ranked) < 2:
        note = "Fewer than two scored sites — nothing to separate."
    elif separable:
        note = (
            "Every adjacent pair is separated by more than the mean of their ± bands, "
            "so this ordering is supported by the evidence."
        )
    else:
        pairs = ", ".join(f"{x} / {y}" for x, y in overlapping)
        note = (
            f"{len(overlapping)} adjacent pair(s) overlap within their confidence bands "
            f"({pairs}). The ordering is not supported by the evidence — compare them on "
            f"the win/lose reasons below, not on the score."
        )

    # What nobody measured. These are the questions the comparison assumes away
    # equally for every candidate, which is exactly when an assumption is invisible.
    measured_anywhere = {f for s in per_site.values() for f in s}
    blind = []
    for fid, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        if fid in measured_anywhere:
            continue
        blind.append({
            "factor_id": fid,
            "name": factors[fid]["name"],
            "domain": factors[fid]["domain"],
            "weight": w,
        })

    comparable = 1.0 - (sum(b["weight"] for b in blind) / total_w)

    return Comparison(
        profile=profile,
        sites=sorted(out_sites, key=lambda s: (s.score is None, -(s.score or 0))),
        separable=separable,
        separability_note=note,
        overlapping_pairs=overlapping,
        shared_blind_spots=blind[:12],
        comparable_fraction=round(comparable, 3),
    )

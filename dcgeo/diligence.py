"""The decision layer: blockers, sensitivity, and the brief.

A score is not a decision. This module turns a scored Analysis into the four
things somebody actually has to act on:

  1. **Decision** — can this site support a profitable data center? Including,
     honestly and most often, "not yet decidable".
  2. **Blockers** — the specific open questions preventing a decision, each with
     the counterparty who can close it.
  3. **Sensitivity** — which factors could flip the verdict, computed by asking
     the real scorer what happens at the best and worst plausible resolution of
     each factor, one at a time.
  4. **Verification queue** — what to go and find out next, in order.

Everything here is arithmetic over the evidence ledger. No estimates enter, and
no number appears that was not either measured or derived from measurements by
code in this file. Where the system cannot answer, the brief says so in the
`decision` field rather than degrading to a confident-sounding score.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .models import Analysis, ProfileScore, Tier
from .provenance import annotate
from .registry import load_factors, load_gates, load_profiles, load_verification
from .scoring import score_profile, verdict_for

# Decisions, worst to best. Deliberately four states, because the third one —
# "we do not know yet" — is the answer most screening produces and the answer
# most tools refuse to give.
NO_GO = "NO-GO"
NOT_PROVEN = "NOT PROVEN"
CONDITIONAL = "PROCEED WITH CONDITIONS"
PROCEED = "PROCEED"

SEVERITY_RANK = {"fatal": 0, "major": 1, "minor": 2}


@dataclass
class Blocker:
    """One open question standing between this evidence and a decision."""

    blocker_id: str
    kind: str            # gate_fail | gate_unverified | gate_condition | gate_undecidable
                         # | domain_blackout | unknown_material | stale | weak_evidence
    severity: str        # fatal | major | minor
    title: str
    why: str             # why it blocks the decision, not why it is bad
    resolve: str         # the artifact that closes it
    owner: str           # the counterparty who can produce that artifact
    factor_id: str | None = None
    gate_id: str | None = None
    domain: str | None = None
    points_at_risk: float | None = None      # score swing tied to this question
    typical_weeks: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Swing:
    """What one factor could do to the score if it resolved at its extremes."""

    factor_id: str
    name: str
    domain: str
    weight: float
    known: bool
    tier: Tier
    current_normalized: float | None
    score_if_best: float | None
    score_if_worst: float | None
    swing: float                    # best - worst, in score points
    flips_verdict: bool             # best and worst land in different verdict bands
    verdict_if_best: str
    verdict_if_worst: str
    gate_critical: bool             # a hard gate reads this factor and cannot decide without it

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerifyItem:
    """One entry in the ordered list of what to find out next."""

    rank: int
    factor_id: str
    question: str
    owner: str
    artifact: str
    points_at_risk: float
    gate_critical: bool
    typical_weeks: tuple[int, int] | None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiligenceBrief:
    profile: str
    decision: str
    headline: str                   # the answer, in one paragraph
    can_answer_profitability: bool
    profitability_basis: str
    score: float | None
    band: float
    confidence: float
    measured_fraction: float
    verdict: str
    decision_weight_measured: float           # share of *decision weight*, not factor count
    domain_coverage: dict[str, dict[str, Any]] = field(default_factory=dict)
    blockers: list[Blocker] = field(default_factory=list)
    swing_factors: list[Swing] = field(default_factory=list)
    verification_queue: list[VerifyItem] = field(default_factory=list)
    evidence_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["blockers"] = [b.to_dict() for b in self.blockers]
        d["swing_factors"] = [s.to_dict() for s in self.swing_factors]
        d["verification_queue"] = [v.to_dict() for v in self.verification_queue]
        return d


# ── verification routing ─────────────────────────────────────────────────────

def verification_for(factor_id: str, country: str | None = None) -> dict[str, Any]:
    """Who must answer this factor, and with what artifact.

    Falls back to the domain default. Country overrides exist because the
    counterparty for a grid question in India is not the counterparty in the US.
    """
    reg = load_verification()
    spec = load_factors().get(factor_id, {})
    domain = spec.get("domain", "")
    out = dict(reg.get("domain_defaults", {}).get(domain, {}))
    entry = reg.get("factors", {}).get(factor_id)
    if entry:
        out.update({k: v for k, v in entry.items() if k != "by_country"})
        if country and (by := entry.get("by_country", {}).get(country)):
            out.update(by)
    out.setdefault("owner", "Not routed — no counterparty registered for this factor")
    out.setdefault("artifact", "Undefined; add an entry to config/verification.yaml")
    return out


def _gate_factors() -> dict[str, str]:
    """factor_id -> gate_id, for factors a hard gate reads."""
    return {
        fid: spec["gate"] for fid, spec in load_factors().items() if spec.get("gate")
    }


# ── sensitivity ──────────────────────────────────────────────────────────────

def sensitivity(
    analysis: Analysis, profile: str, base: ProfileScore | None = None
) -> list[Swing]:
    """For each weighted factor, what the score becomes at its best and worst resolution.

    Computed by running the real scorer with a counterfactual on that one factor,
    so the sensitivity can never disagree with the score it is explaining. The
    resolved tier is assumed to be the factor's own `best_tier`, i.e. this answers
    "what if somebody went and measured this properly", not "what if we guessed".

    These are pre-gate scores. Gate outcomes turn on raw values, not normalized
    ones, so simulating them would require inventing raw values — instead, factors
    a gate reads are flagged `gate_critical` and handled as blockers.
    """
    factors = load_factors()
    base = base or score_profile(analysis, profile, analysis.weight_overrides)
    gate_map = _gate_factors()
    out: list[Swing] = []

    for fs in base.factor_scores:
        spec = factors[fs.factor_id]
        resolved_tier: Tier = spec.get("best_tier", "C")
        hi = score_profile(
            analysis, profile, analysis.weight_overrides,
            counterfactual={fs.factor_id: (100.0, resolved_tier)},
        )
        lo = score_profile(
            analysis, profile, analysis.weight_overrides,
            counterfactual={fs.factor_id: (0.0, resolved_tier)},
        )
        hs, ls = hi.score, lo.score
        swing = round((hs - ls), 2) if hs is not None and ls is not None else 0.0
        vb, vw = verdict_for(hs), verdict_for(ls)
        out.append(
            Swing(
                factor_id=fs.factor_id,
                name=spec["name"],
                domain=fs.domain,
                weight=fs.weight,
                known=fs.normalized is not None,
                tier=fs.tier,
                current_normalized=fs.normalized,
                score_if_best=hs,
                score_if_worst=ls,
                swing=swing,
                flips_verdict=vb != vw,
                verdict_if_best=vb,
                verdict_if_worst=vw,
                gate_critical=(
                    fs.factor_id in gate_map and fs.normalized is None
                ),
            )
        )
    return sorted(out, key=lambda s: (-s.swing, -s.weight))


# ── blockers ─────────────────────────────────────────────────────────────────



def _domain_coverage(ps: ProfileScore) -> dict[str, dict[str, Any]]:
    """Per-domain: how much of it is measured, and whether it reached the score.

    The headline is a weighted mean over domains that have data. Which domains
    those were is not a detail — it is the shape of the answer.
    """
    factors = load_factors()
    by: dict[str, list[Any]] = {}
    for fs in ps.factor_scores:
        by.setdefault(fs.domain, []).append(fs)
    out: dict[str, dict[str, Any]] = {}
    for d, items in by.items():
        known = [i for i in items if i.normalized is not None]
        wsum = sum(i.weight for i in items) or 1.0
        out[d] = {
            "domain_weight": float(
                factors[items[0].factor_id]["domain_weight"].get(ps.profile, 1)
            ),
            "factors": len(items),
            "measured": len(known),
            "weight_measured": round(sum(i.weight for i in known) / wsum, 3),
            "score": ps.domain_scores.get(d),
            "in_score": bool(known),
        }
    return out


def _dark_domains(
    ps: ProfileScore, swing_by_id: dict[str, Swing]
) -> dict[str, dict[str, Any]]:
    """Domains where not a single factor was measured, with what that costs.

    Reported separately from ordinary unknowns because the consequence is
    different: an unknown factor lowers a domain's confidence, but a dark domain
    leaves the aggregate altogether.
    """
    factors = load_factors()
    by_domain: dict[str, list[Any]] = {}
    for fs in ps.factor_scores:
        by_domain.setdefault(fs.domain, []).append(fs)

    dweight = {
        d: float(factors[items[0].factor_id]["domain_weight"].get(ps.profile, 1))
        for d, items in by_domain.items()
    }
    total_dw = sum(dweight.values()) or 1.0
    scored = sum(
        1 for d, items in by_domain.items()
        if any(i.normalized is not None for i in items)
    )

    out: dict[str, dict[str, Any]] = {}
    for d, items in by_domain.items():
        if any(i.normalized is not None for i in items):
            continue
        top = max(items, key=lambda i: (swing_by_id[i.factor_id].swing
                                        if i.factor_id in swing_by_id else 0.0, i.weight))
        out[d] = {
            "domain_weight": dweight[d],
            "total_domain_weight": total_dw,
            "factor_count": len(items),
            "scored_domains": scored,
            "top_factor_id": top.factor_id,
            "top_factor": factors[top.factor_id]["name"],
            "top_swing": round(
                swing_by_id[top.factor_id].swing if top.factor_id in swing_by_id else 0.0, 2
            ),
            "gate_factors": [i.factor_id for i in items if factors[i.factor_id].get("gate")],
        }
    return out


def _gate_name(gate_id: str) -> str:
    for g in load_gates():
        if g["id"] == gate_id:
            return g["name"]
    return gate_id


def blockers(
    analysis: Analysis, profile: str, swings: list[Swing]
) -> list[Blocker]:
    """Everything standing between this evidence and a decision, ranked.

    Six kinds, in descending order of how much trouble they cause: a failed gate,
    a gate whose input is missing so it could not decide at all, a whole domain
    with no data, a gate condition, an unknown big enough to move the verdict, and
    evidence too old or too weak to bet on.

    Blockers are deduplicated downward: a dark domain absorbs the individual
    unknowns inside it, because "dispatch the regulatory analyst" is one action,
    not seven.
    """
    cfg = load_profiles().get("decision", {})
    material = float(cfg.get("material_swing_points", 4.0))
    country = analysis.site.country
    factors = load_factors()
    swing_by_id = {s.factor_id: s for s in swings}
    ps = analysis.profiles.get(profile)
    band = ps.band if ps else 0.0
    gate_map = _gate_factors()
    dark = _dark_domains(ps, swing_by_id) if ps else {}
    out: list[Blocker] = []

    # Gates whose input is missing. Reported once, at the factor, not twice.
    undecidable_gates = {
        gid for fid, gid in gate_map.items()
        if (sw := swing_by_id.get(fid)) and not sw.known
    }

    # 1. Gates that returned a verdict other than PASS.
    for g in analysis.gates:
        if g.outcome == "PASS":
            continue
        if g.outcome == "CONDITIONAL" and g.gate_id in undecidable_gates:
            # Conditional only because it had nothing to read. Covered below by the
            # gate_undecidable / domain_blackout blocker naming the missing factor,
            # which is the one somebody can actually act on.
            continue
        if g.outcome == "FAIL":
            kind = "gate_unverified" if g.low_confidence else "gate_fail"
            why = (
                "A fatal gate failed, but on Tier C/D evidence — the site is not dead "
                "until this is confirmed against a primary source."
                if g.low_confidence else
                "A fatal gate failed on evidence strong enough to act on. Nothing "
                "downstream of this changes the answer."
            )
        else:
            kind, why = "gate_condition", (
                "The site is not disqualified, but the score is capped until this "
                "condition is resolved."
            )
        # Attribute the gate's risk to the highest-swing factor it actually reads,
        # so a gate blocker sorts against factor blockers on the same scale.
        read = [f for f, gg in gate_map.items() if gg == g.gate_id]
        owner_factor = max(
            read, key=lambda f: swing_by_id[f].swing if f in swing_by_id else 0.0,
            default="",
        )
        at_risk = round(
            max((swing_by_id[f].swing for f in read if f in swing_by_id), default=0.0), 2
        ) or None
        out.append(Blocker(
            blocker_id=f"blk.{g.gate_id}",
            kind=kind,
            severity="fatal" if g.outcome == "FAIL" else "major",
            title=g.name,
            why=f"{g.reason} {why}",
            resolve=g.remediation_hint or "No remediation path registered for this gate.",
            owner=verification_for(owner_factor, country)["owner"],
            gate_id=g.gate_id,
            factor_id=owner_factor or None,
            domain=factors[owner_factor]["domain"] if owner_factor else None,
            points_at_risk=at_risk,
        ))

    # 2. Gates that could not decide, because the factor they read is missing.
    #    Distinct from a gate condition: the gate did not decide leniently, it had
    #    nothing to decide on. Suppressed inside a dark domain, which reports the
    #    same problem at the level where the fix actually happens.
    for fid, gid in gate_map.items():
        sw = swing_by_id.get(fid)
        if not sw or sw.known or sw.domain in dark:
            continue
        v = verification_for(fid, country)
        out.append(Blocker(
            blocker_id=f"blk.undecidable.{fid}",
            kind="gate_undecidable",
            severity="fatal",
            title=f"{factors[fid]['name']} is unmeasured, and {_gate_name(gid)} depends on it",
            why=(
                f"This gate is a knockout check and its input is missing, so its "
                f"result is not evidence of anything. Resolving the factor moves the "
                f"score by up to {sw.swing:.0f} points on its own."
            ),
            resolve=v["artifact"],
            owner=v["owner"],
            factor_id=fid,
            gate_id=gid,
            domain=sw.domain,
            points_at_risk=sw.swing,
            typical_weeks=tuple(v["typical_weeks"]) if v.get("typical_weeks") else None,
        ))

    # 3. Domains with nothing measured at all.
    #    A dark domain is not "several unknowns", it is a structural hole. The
    #    aggregate is a weighted mean over domains that have data, so a dark domain
    #    drops out of the denominator and the headline is quietly computed over a
    #    subset of the model. One loud blocker, not seven quiet ones.
    for domain, info in sorted(dark.items(), key=lambda kv: -kv[1]["top_swing"]):
        gates_dark = info["gate_factors"]
        out.append(Blocker(
            blocker_id=f"blk.blackout.{domain}",
            kind="domain_blackout",
            severity="fatal" if gates_dark else "major",
            title=f"Nothing measured in {domain} — all {info['factor_count']} factors dark",
            why=(
                f"This domain carries weight {info['domain_weight']:.0f} of "
                f"{info['total_domain_weight']:.0f} in this profile and has no values at "
                f"all, so it is excluded from the score: the headline number is a "
                f"weighted mean over the {info['scored_domains']} domains that do have "
                f"data, not over all {info['scored_domains'] + len(dark)}."
                + (
                    f" It also holds the input to {len(gates_dark)} knockout check(s), "
                    f"which are therefore being decided blind."
                    if gates_dark else ""
                )
            ),
            resolve=(
                f"Dispatch the {domain} analyst. Highest-swing factor in the domain is "
                f"{info['top_factor']} at {info['top_swing']:.0f} points."
            ),
            owner=verification_for(info["top_factor_id"], country)["owner"],
            factor_id=info["top_factor_id"],
            domain=domain,
            points_at_risk=info["top_swing"],
        ))

    # 4. Unknowns large enough to matter, outside the domains already reported dark.
    for sw in swings:
        if sw.known or sw.gate_critical or sw.swing < material or sw.domain in dark:
            continue
        v = verification_for(sw.factor_id, country)
        out.append(Blocker(
            blocker_id=f"blk.unknown.{sw.factor_id}",
            kind="unknown_material",
            severity="major" if sw.flips_verdict or sw.swing >= band else "minor",
            title=f"{sw.name} is unmeasured",
            why=(
                f"Resolving this moves the score by up to {sw.swing:.0f} points"
                + (
                    f", straddling the boundary between '{sw.verdict_if_worst}' and "
                    f"'{sw.verdict_if_best}' — the verdict is not determined by the "
                    f"evidence on hand."
                    if sw.flips_verdict else
                    f", against a ± band of {band:.0f}."
                )
            ),
            resolve=v["artifact"],
            owner=v["owner"],
            factor_id=sw.factor_id,
            domain=sw.domain,
            points_at_risk=sw.swing,
            typical_weeks=tuple(v["typical_weeks"]) if v.get("typical_weeks") else None,
        ))

    # 5. Evidence that exists but should not be leaned on.
    for fs in (ps.factor_scores if ps else []):
        sw = swing_by_id.get(fs.factor_id)
        if fs.normalized is None or not sw or sw.swing < material:
            continue
        v = verification_for(fs.factor_id, country)
        if fs.freshness == "stale":
            out.append(Blocker(
                blocker_id=f"blk.stale.{fs.factor_id}",
                kind="stale",
                severity="major",
                title=f"{factors[fs.factor_id]['name']} is measured, but stale",
                why=(
                    f"Retrieved {fs.age_days:.0f} days ago from {fs.source}, more than "
                    f"twice that source's refresh window, while carrying "
                    f"{sw.swing:.0f} points of swing."
                ),
                resolve="Re-measure — `dcgeo measure` refreshes it once past the cache TTL.",
                owner=v["owner"],
                factor_id=fs.factor_id,
                domain=fs.domain,
                points_at_risk=sw.swing,
            ))
        elif fs.tier == "D":
            out.append(Blocker(
                blocker_id=f"blk.weak.{fs.factor_id}",
                kind="weak_evidence",
                severity="minor",
                title=f"{factors[fs.factor_id]['name']} rests on a model, not a measurement",
                why=(
                    f"Tier D — modeled or assumed — and carrying {sw.swing:.0f} points "
                    f"of swing, so it is doing real work in the score."
                ),
                resolve=v["artifact"],
                owner=v["owner"],
                factor_id=fs.factor_id,
                domain=fs.domain,
                points_at_risk=sw.swing,
                typical_weeks=tuple(v["typical_weeks"]) if v.get("typical_weeks") else None,
            ))

    return sorted(
        out, key=lambda b: (SEVERITY_RANK[b.severity], -(b.points_at_risk or 0.0))
    )


# ── verification queue ───────────────────────────────────────────────────────

def verification_queue(
    analysis: Analysis, profile: str, swings: list[Swing], limit: int = 8
) -> list[VerifyItem]:
    """What to go and find out next, in order of how much of the decision it settles.

    Gate-critical unknowns come first regardless of swing: a knockout check that
    cannot be evaluated is worth more than any number of score points, because it
    is the one that can make the rest of the work irrelevant.
    """
    factors = load_factors()
    country = analysis.site.country
    ps = analysis.profiles.get(profile)
    stale_or_weak = {
        fs.factor_id
        for fs in (ps.factor_scores if ps else [])
        if fs.normalized is not None and (fs.freshness == "stale" or fs.tier == "D")
    }

    candidates = [
        s for s in swings
        if (not s.known or s.factor_id in stale_or_weak) and s.swing > 0
    ]
    candidates.sort(key=lambda s: (not s.gate_critical, -s.swing, -s.weight))

    out: list[VerifyItem] = []
    for i, s in enumerate(candidates[:limit], start=1):
        v = verification_for(s.factor_id, country)
        out.append(VerifyItem(
            rank=i,
            factor_id=s.factor_id,
            question=factors[s.factor_id]["question"],
            owner=v["owner"],
            artifact=v["artifact"],
            points_at_risk=s.swing,
            gate_critical=s.gate_critical,
            typical_weeks=tuple(v["typical_weeks"]) if v.get("typical_weeks") else None,
            note=v.get("note", "").strip() or None,
        ))
    return out


# ── the brief ────────────────────────────────────────────────────────────────

def _profitability(analysis: Analysis) -> tuple[bool, str]:
    """Whether the ledger can support a profitability statement at all.

    Suitability and profitability are different questions. A site can clear every
    physical constraint and still lose money on the tariff. This refuses to let
    the score be read as a profitability answer unless the inputs exist.
    """
    needed = load_profiles().get("decision", {}).get("profitability_factors", [])
    mmap = analysis.measurement_map()
    have = [f for f in needed if (m := mmap.get(f)) and m.is_known]
    missing = [f for f in needed if f not in have]
    factors = load_factors()
    if not missing:
        return True, (
            "Every cost input the model needs is measured: "
            + ", ".join(factors[f]["name"] for f in have) + "."
        )
    return False, (
        f"{len(missing)} of {len(needed)} cost inputs are unmeasured ("
        + ", ".join(factors[f]["name"] for f in missing)
        + "), so the score is a suitability screen, not a return."
    )


def build_brief(analysis: Analysis, profile: str) -> DiligenceBrief:
    """The whole decision, assembled. Persisted into analysis.json under `diligence`."""
    ps = analysis.profiles.get(profile) or score_profile(
        analysis, profile, analysis.weight_overrides
    )
    max_flips = int(
        load_profiles().get("decision", {}).get("max_flipping_unknowns_for_proceed", 0)
    )

    sw = sensitivity(analysis, profile, ps)
    blk = blockers(analysis, profile, sw)
    queue = verification_queue(analysis, profile, sw)
    can_profit, profit_basis = _profitability(analysis)

    flipping = [s for s in sw if not s.known and s.flips_verdict]
    fatal = [b for b in blk if b.severity == "fatal"]
    hard_fail = [b for b in blk if b.kind == "gate_fail"]

    # Decision. Order matters: a confirmed fatal gate ends it; otherwise anything
    # that leaves the verdict undetermined lands on NOT PROVEN rather than on a
    # number, because a number here would be read as an answer.
    if hard_fail:
        decision = NO_GO
        headline = (
            f"No. {hard_fail[0].title} — {hard_fail[0].why.split('.')[0]}. "
            "This is a categorical exclusion, not a low score, so the remaining "
            "factors do not change the answer."
        )
    elif fatal or len(flipping) > max_flips or not ps.publishable:
        decision = NOT_PROVEN
        parts = []
        undecidable = [b for b in fatal if b.kind == "gate_undecidable"]
        blackouts = [b for b in fatal if b.kind == "domain_blackout"]
        if undecidable:
            parts.append(
                f"{len(undecidable)} knockout check"
                f"{'s' if len(undecidable) > 1 else ''} cannot be evaluated at all "
                f"because the factor each one reads is unmeasured"
            )
        if blackouts:
            parts.append(
                f"the {', '.join(b.domain or '?' for b in blackouts)} "
                f"domain{'s have' if len(blackouts) > 1 else ' has'} no data at all "
                f"and drop{'' if len(blackouts) > 1 else 's'} out of the score"
            )
        if flipping:
            parts.append(
                f"{len(flipping)} unmeasured factor"
                f"{'s' if len(flipping) > 1 else ''} could each move the verdict "
                f"across a threshold on its own"
            )
        if not ps.publishable:
            parts.append(
                f"only {ps.measured_fraction:.0%} of the decision weight is measured"
            )
        headline = (
            "Not yet — and the reason is missing evidence, not a bad site. "
            + "; ".join(parts).capitalize() + ". "
            + ("Profitability in particular is unanswerable here: " + profit_basis + " "
               if not can_profit else "")
            + "The verification queue is ordered by how much of the decision each "
              "answer settles."
        )
    elif [b for b in blk if b.severity == "major"]:
        decision = CONDITIONAL
        cap = ps.capped_by
        headline = (
            f"Conditionally. Every knockout check is satisfied and "
            f"{ps.measured_fraction:.0%} of the decision weight is measured, "
            f"scoring {ps.score:.0f} ± {ps.band:.0f}"
            + (f", capped by {cap}" if cap else "")
            + f". {len([b for b in blk if b.severity == 'major'])} condition(s) must be "
              "cleared before capital is committed; they are listed below with the "
              "counterparty who can clear each one."
        )
    else:
        decision = PROCEED
        headline = (
            f"Yes, on the evidence collected. All knockout checks pass, "
            f"{ps.measured_fraction:.0%} of the decision weight is measured at "
            f"confidence {ps.confidence:.2f}, and no unmeasured factor can move the "
            f"verdict across a threshold. Score {ps.score:.0f} ± {ps.band:.0f}. "
            + profit_basis
        )
    tiers: dict[str, int] = {}
    fresh: dict[str, int] = {}
    for fs in ps.factor_scores:
        key = fs.tier if fs.normalized is not None else "unknown"
        tiers[key] = tiers.get(key, 0) + 1
        if fs.normalized is not None:
            fresh[fs.freshness] = fresh.get(fs.freshness, 0) + 1

    return DiligenceBrief(
        profile=profile,
        decision=decision,
        headline=" ".join(headline.split()),
        can_answer_profitability=can_profit,
        profitability_basis=profit_basis,
        score=ps.score,
        band=ps.band,
        confidence=ps.confidence,
        measured_fraction=ps.measured_fraction,
        verdict=ps.verdict,
        decision_weight_measured=ps.measured_fraction,
        domain_coverage=_domain_coverage(ps),
        blockers=blk,
        swing_factors=sw,
        verification_queue=queue,
        evidence_summary={
            "tiers": tiers,
            "freshness": fresh,
            "provenance": [
                annotate(m) for m in analysis.measurement_map().values() if m.is_known
            ],
        },
    )


def attach(analysis: Analysis) -> None:
    """Compute and store a brief for every scored profile. Called after gating."""
    analysis.diligence = {
        p: build_brief(analysis, p).to_dict() for p in analysis.profiles
    }

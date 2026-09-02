"""Deterministic scoring: normalize -> weight -> aggregate -> confidence.

No LLM touches this file. If an agent disagrees with a score, the fix is to argue
with the factor spec or the measurement, not to override the arithmetic.
"""
from __future__ import annotations

from typing import Any

from .models import Analysis, FactorScore, Measurement, ProfileScore, Tier
from .registry import load_factors, load_profiles


def normalize(spec: dict[str, Any], value: Any) -> float | None:
    """Map a raw factor value to 0-100 using the curve in its spec.

    Piecewise-linear rather than linear because these relationships have knees —
    wet-bulb is nearly free below 18 C and expensive above 24 C. Encoding that in
    YAML keeps it visible and arguable instead of buried in code.
    """
    if value is None:
        return None

    if spec.get("direction") == "categorical":
        cats = spec.get("categories", {})
        if value not in cats:
            return None
        return cats[value]                     # may legitimately be None ("unknown")

    scale = spec.get("scale")
    if not scale:
        # Composite factors arrive pre-normalized on 0-100 from their adapter.
        if "composite_of" in spec:
            return max(0.0, min(100.0, float(value)))
        return None

    pts = scale["points"]
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None

    if x <= pts[0][0]:
        return float(pts[0][1])
    if x >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return float(y0)
            t = (x - x0) / (x1 - x0)
            return float(y0 + t * (y1 - y0))
    return None


def _tier_weight(tier: Tier) -> float:
    return load_profiles()["tier_weights"].get(tier, 0.0)


def score_profile(
    analysis: Analysis,
    profile: str,
    weight_overrides: dict[str, float] | None = None,
) -> ProfileScore:
    """Score one site for one use-case profile."""
    factors = load_factors()
    cfg = load_profiles()
    agg = cfg["aggregation"]
    overrides = weight_overrides or {}
    mmap = analysis.measurement_map()

    fscores: list[FactorScore] = []
    for fid, spec in factors.items():
        weight = float(spec["weights"].get(profile, 0))
        # --weight accepts a factor id or a whole domain name
        if fid in overrides:
            weight = weight * float(overrides[fid])
        elif spec["domain"] in overrides:
            weight = weight * float(overrides[spec["domain"]])
        if weight <= 0:
            continue

        m: Measurement | None = mmap.get(fid)
        raw = m.value if m else None
        tier: Tier = m.tier if m else "unknown"
        norm = normalize(spec, raw) if m else None
        if norm is None:
            tier = "unknown"

        fscores.append(
            FactorScore(
                factor_id=fid,
                domain=spec["domain"],
                raw_value=raw,
                unit=spec.get("unit", ""),
                normalized=norm,
                weight=weight,
                tier=tier,
                tier_weight=_tier_weight(tier),
            )
        )

    # Domain aggregation. Unknowns are excluded from the mean and penalize
    # confidence instead — never substituted with a midpoint.
    by_domain: dict[str, list[FactorScore]] = {}
    for fs in fscores:
        by_domain.setdefault(fs.domain, []).append(fs)

    domain_scores: dict[str, float | None] = {}
    domain_weights: dict[str, float] = {}
    for domain, items in by_domain.items():
        known = [i for i in items if i.normalized is not None]
        if known:
            wsum = sum(i.weight for i in known)
            domain_scores[domain] = round(
                sum(i.normalized * i.weight for i in known) / wsum, 2
            )
        else:
            domain_scores[domain] = None
        spec_any = load_factors()[items[0].factor_id]
        domain_weights[domain] = float(spec_any["domain_weight"].get(profile, 1))

    known_domains = {d: s for d, s in domain_scores.items() if s is not None}
    if known_domains:
        dw = sum(domain_weights[d] for d in known_domains)
        overall = sum(s * domain_weights[d] for d, s in known_domains.items()) / dw
    else:
        overall = None

    # Confidence from the tiers actually achieved, weighted by factor importance.
    total_w = sum(f.weight for f in fscores) or 1.0
    confidence = sum(f.weight * f.tier_weight for f in fscores) / total_w
    measured_fraction = sum(
        f.weight for f in fscores if f.normalized is not None
    ) / total_w

    band = round((1 - confidence) * float(cfg["aggregation"]["band_constant"]), 1)
    publishable = measured_fraction >= float(agg["min_measured_fraction"])

    return ProfileScore(
        profile=profile,
        score=round(overall, 1) if overall is not None else None,
        band=band,
        confidence=round(confidence, 3),
        measured_fraction=round(measured_fraction, 3),
        verdict=verdict_for(overall),
        domain_scores=domain_scores,
        factor_scores=sorted(fscores, key=lambda f: -f.weight),
        publishable=publishable,
    )


def verdict_for(score: float | None) -> str:
    if score is None:
        return "insufficient-data"
    t = load_profiles()["verdict_thresholds"]
    if score >= t["strong_candidate"]:
        return "strong-candidate"
    if score >= t["viable"]:
        return "viable"
    if score >= t["conditional"]:
        return "conditional"
    if score >= t["weak"]:
        return "weak"
    return "poor"


def apply_gates_to_scores(analysis: Analysis) -> None:
    """Gates override scores. A FAIL sets NO-GO; a CONDITIONAL caps the score.

    Called after gate evaluation and profile scoring. Mutates analysis.profiles.
    """
    fatal = [g for g in analysis.gates if g.outcome == "FAIL"]
    caps = [g for g in analysis.gates if g.outcome == "CONDITIONAL" and g.capped_score]

    for ps in analysis.profiles.values():
        if fatal:
            hard = [g for g in fatal if not g.low_confidence]
            if hard:
                ps.verdict = "NO-GO"
                ps.capped_by = hard[0].gate_id
            else:
                ps.verdict = "NO-GO (unverified)"
                ps.capped_by = fatal[0].gate_id
            continue
        if caps and ps.score is not None:
            cap = min(g.capped_score for g in caps)
            if ps.score > cap:
                binding = min(caps, key=lambda g: g.capped_score)
                ps.score = cap
                ps.verdict = verdict_for(cap)
                ps.capped_by = binding.gate_id

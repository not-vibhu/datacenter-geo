"""Per-datapoint provenance: where a number came from, when, and how much it is worth now.

Tier answers "how was this obtained". It does not answer "is it still true". A
Tier A interconnection queue reading from three years ago is stale in a way the
tier alone cannot express, and a system that treats it as fresh will confidently
recommend a site on a number that has since moved.

So confidence for a single datapoint is two-dimensional:

    datapoint_confidence = tier_weight * freshness_multiplier

Both halves come from config (profiles.yaml `tier_weights` and `freshness`), and
the TTL each measurement is judged against comes from its source's declared
`ttl_days` in sources.yaml. Nothing here estimates anything — if a measurement
carries no timestamp we say `undated` and apply the undated multiplier rather
than assuming it is current.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from .models import Measurement, Tier
from .registry import load_profiles, load_sources

Freshness = Literal["fresh", "aging", "stale", "undated"]

FRESHNESS_LABEL: dict[str, str] = {
    "fresh": "within the source's refresh window",
    "aging": "past its refresh window but under twice it",
    "stale": "more than twice the source's refresh window old",
    "undated": "no retrieval timestamp recorded",
}


def _cfg() -> dict[str, Any]:
    return load_profiles().get("freshness", {})


def tier_weight(tier: Tier) -> float:
    return float(load_profiles()["tier_weights"].get(tier, 0.0))


def source_ttl_days(source: str | None) -> int | None:
    """Declared cache lifetime for a source, or None if it is not registered."""
    if not source:
        return None
    spec = load_sources().get(source)
    if not spec:
        return None
    ttl = spec.get("ttl_days")
    return int(ttl) if ttl is not None else None


def age_days(retrieved: str | None, *, now: datetime | None = None) -> float | None:
    if not retrieved:
        return None
    try:
        ts = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return max(0.0, ((now or datetime.now(UTC)) - ts).total_seconds() / 86400.0)


def freshness_of(
    source: str | None, retrieved: str | None, *, now: datetime | None = None
) -> tuple[Freshness, float | None, int | None]:
    """(freshness, age_days, ttl_days) for one datapoint."""
    age = age_days(retrieved, now=now)
    ttl = source_ttl_days(source)
    if age is None:
        return "undated", None, ttl
    if ttl is None:
        ttl = int(_cfg().get("default_ttl_days", 180))
    if age <= ttl:
        return "fresh", age, ttl
    if age <= ttl * 2:
        return "aging", age, ttl
    return "stale", age, ttl


def freshness_multiplier(f: Freshness) -> float:
    c = _cfg()
    return float(
        {
            "fresh": c.get("fresh_multiplier", 1.0),
            "aging": c.get("aging_multiplier", 0.85),
            "stale": c.get("stale_multiplier", 0.55),
            "undated": c.get("undated_multiplier", 0.70),
        }[f]
    )


def annotate(m: Measurement, *, now: datetime | None = None) -> dict[str, Any]:
    """Provenance record for one measurement, ready to serialize or render.

    Every field a reader needs to decide whether to trust the number, in one place:
    what it says, who said it, when, how it was obtained, and what that is worth.
    """
    f, age, ttl = freshness_of(m.source, m.retrieved, now=now)
    tw = tier_weight(m.tier)
    fm = freshness_multiplier(f) if m.is_known else 0.0
    return {
        "measurement_id": m.id,
        "factor_id": m.factor_id,
        "known": m.is_known,
        "source": m.source,
        "source_url": m.source_url,
        "retrieved": m.retrieved,
        "age_days": None if age is None else round(age, 1),
        "ttl_days": ttl,
        "freshness": f if m.is_known else "undated",
        "freshness_reason": FRESHNESS_LABEL[f if m.is_known else "undated"],
        "tier": m.tier,
        "tier_weight": tw,
        "confidence": round(tw * fm, 3),
        "unknown_reason": m.unknown_reason,
    }


def evidence_weight(m: Measurement | None, *, now: datetime | None = None) -> float:
    """Tier weight discounted for age. Zero for a missing or unknown measurement.

    This is what feeds profile confidence, so an old number widens the ± band the
    same way a weak tier does.
    """
    if m is None or not m.is_known:
        return 0.0
    f, _, _ = freshness_of(m.source, m.retrieved, now=now)
    return tier_weight(m.tier) * freshness_multiplier(f)

"""Core data model. Four objects: Measurement, Claim, Site, Analysis.

Everything the system produces is a view over these. They are deliberately
plain dataclasses with explicit serialization — this data outlives any
particular version of the code and must stay readable without it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal

Tier = Literal["A", "B", "C", "D", "unknown"]
GateOutcome = Literal["PASS", "CONDITIONAL", "FAIL"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Measurement:
    """One value, about one place, from one source, at one time.

    A Measurement with value=None is not a failure to record — it IS the record
    that the value is unknown, and it carries the reason. This distinction is
    load-bearing: unknowns must lower confidence, never silently default.
    """

    factor_id: str
    value: Any                      # float | str | None
    unit: str
    tier: Tier
    source: str
    source_url: str | None = None
    retrieved: str = field(default_factory=_now)
    geometry_ref: str | None = None
    raw: dict[str, Any] | None = None
    unknown_reason: str | None = None
    notes: str | None = None

    @property
    def is_known(self) -> bool:
        return self.value is not None

    @property
    def id(self) -> str:
        key = f"{self.factor_id}|{self.source}|{self.geometry_ref}|{self.retrieved}"
        return "m_" + hashlib.sha256(key.encode()).hexdigest()[:12]

    def __post_init__(self) -> None:
        if self.value is None:
            self.tier = "unknown"
            if not self.unknown_reason:
                self.unknown_reason = "not measured; no reason recorded"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        return d


@dataclass
class Claim:
    """A judgment made about measurements by an agent.

    Carries the measurement ids it rests on, so it can be invalidated
    automatically when an underlying measurement is refreshed and changes.
    """

    claim_id: str
    factor_id: str | None
    statement: str
    agent: str
    tier: Tier
    based_on: list[str] = field(default_factory=list)     # Measurement ids
    citations: list[str] = field(default_factory=list)    # URLs
    created: str = field(default_factory=_now)
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Site:
    """An area of interest."""

    site_id: str
    name: str
    centroid: tuple[float, float]          # (lat, lon)
    radius_km: float = 10.0
    geometry: dict[str, Any] | None = None  # GeoJSON if a polygon was supplied
    country: str | None = None
    admin1: str | None = None              # state / province
    admin2: str | None = None              # county / district
    utility: str | None = None
    market: str | None = None              # ISO/RTO, DISCOM, provincial grid
    origin: str = "manual"                 # manual | prospector | reference
    hypothesis: str | None = None          # the falsifiable claim, if prospector-generated
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_geojson(self) -> dict[str, Any]:
        geom = self.geometry or {
            "type": "Point",
            "coordinates": [self.centroid[1], self.centroid[0]],
        }
        return {
            "type": "Feature",
            "geometry": geom,
            "properties": {
                k: v for k, v in self.to_dict().items() if k not in ("geometry", "centroid")
            },
        }


@dataclass
class GateResult:
    gate_id: str
    name: str
    outcome: GateOutcome
    reason: str
    evidence_tier: Tier = "unknown"
    low_confidence: bool = False           # gate decided on Tier C/D evidence
    capped_score: float | None = None
    remediation_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FactorScore:
    factor_id: str
    domain: str
    raw_value: Any
    unit: str
    normalized: float | None               # 0-100, None when unknown
    weight: float
    tier: Tier
    tier_weight: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProfileScore:
    profile: str
    score: float | None
    band: float
    confidence: float
    measured_fraction: float
    verdict: str
    domain_scores: dict[str, float | None] = field(default_factory=dict)
    factor_scores: list[FactorScore] = field(default_factory=list)
    capped_by: str | None = None
    publishable: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["factor_scores"] = [f.to_dict() for f in self.factor_scores]
        return d


@dataclass
class Recommendation:
    factor_id: str
    gap: str
    intervention: str
    cost_low_usd: float | None
    cost_high_usd: float | None
    cost_basis: str
    timeline_months: tuple[int, int] | None
    score_gain: float | None
    actor: str                             # who must act: developer | utility | county | state
    confidence: Tier = "D"

    @property
    def leverage(self) -> float | None:
        """Score points per $10M. The number that turns assessment into decision aid."""
        if self.score_gain is None or not self.cost_high_usd:
            return None
        mid = ((self.cost_low_usd or 0) + self.cost_high_usd) / 2
        if mid <= 0:
            return None
        return round(self.score_gain / (mid / 1e7), 3)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["leverage_pts_per_10m"] = self.leverage
        return d


@dataclass
class Analysis:
    """One scoring run over one site. Append-only; re-runs create children."""

    run_id: str
    site: Site
    created: str = field(default_factory=_now)
    parent_run: str | None = None
    assumptions: dict[str, Any] = field(default_factory=dict)
    weight_overrides: dict[str, float] = field(default_factory=dict)
    cooling_assumption: str = "hybrid_adiabatic"
    measurements: list[Measurement] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    gates: list[GateResult] = field(default_factory=list)
    profiles: dict[str, ProfileScore] = field(default_factory=dict)
    red_team: list[str] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)

    def measurement_map(self) -> dict[str, Measurement]:
        """Latest measurement per factor, preferring the best tier then most recent."""
        order = {"A": 0, "B": 1, "C": 2, "D": 3, "unknown": 4}
        best: dict[str, Measurement] = {}
        for m in self.measurements:
            cur = best.get(m.factor_id)
            if cur is None:
                best[m.factor_id] = m
            elif (order[m.tier], cur.retrieved) < (order[cur.tier], m.retrieved):
                best[m.factor_id] = m
        return best

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created": self.created,
            "parent_run": self.parent_run,
            "site": self.site.to_dict(),
            "assumptions": self.assumptions,
            "weight_overrides": self.weight_overrides,
            "cooling_assumption": self.cooling_assumption,
            "measurements": [m.to_dict() for m in self.measurements],
            "claims": [c.to_dict() for c in self.claims],
            "gates": [g.to_dict() for g in self.gates],
            "profiles": {k: v.to_dict() for k, v in self.profiles.items()},
            "red_team": self.red_team,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

"""Measurement dispatcher — runs adapters, never lets one failure abort a run.

The contract: every factor in the registry gets a Measurement, even if that
Measurement is `unknown`. Silence is not an acceptable output, because a missing
factor and a factor that could not be measured are different facts.
"""
from __future__ import annotations

import traceback
from collections.abc import Callable

from .adapters import climate, context, flood, overpass, peeringdb, solar, terrain
from .adapters.base import unknown
from .adapters.overpass import gas_pipeline_distance
from .models import Measurement
from .registry import load_factors

# domain -> [(label, callable(lat, lon) -> list[Measurement])]
DISPATCH: dict[str, list[tuple[str, Callable]]] = {
    "power": [
        ("transmission", overpass.nearest_transmission),
        ("substations", overpass.substations),
        ("onsite_generation", lambda lat, lon: onsite_generation(lat, lon)),
    ],
    "water": [
        ("wetbulb", climate.wetbulb_hours),
        ("reclaimed", overpass.wwtp_distance),
    ],
    "climate": [
        ("free_cooling", climate.free_cooling_hours),
        ("heat_trend", climate.heat_projection),
        ("flood", flood.flood_return_period),
    ],
    "land": [
        ("slope", terrain.slope_stats),
        ("developable", overpass.developable_area),
        ("brownfield", overpass.brownfield_signals),
    ],
    "connectivity": [
        ("ixp", peeringdb.nearest_ixp),
        ("carriers", peeringdb.carrier_count),
        ("fiber", overpass.fiber_proximity),
    ],
    "regulatory": [],       # Tier C — agent web research, no adapter
    "community": [
        ("dwellings", overpass.dwellings_within),
    ],
    "economics": [
        ("port_rail", overpass.port_rail_access),
    ],
}


def onsite_generation(lat: float, lon: float) -> list[Measurement]:
    """pwr.onsite_generation_potential — composite index.

    Gas pipeline proximity carries the most weight because behind-the-meter gas can
    be deployed in 18-30 months against 4-7 years for a grid interconnection. Solar
    and wind cannot firm a data center load and are counted only for their
    contribution to a hybrid or bridging strategy.
    """
    fid = "pwr.onsite_generation_potential"
    parts: dict[str, float | None] = {}
    try:
        parts["gas_pipeline_km"] = gas_pipeline_distance(lat, lon)
    except Exception as e:
        parts["gas_pipeline_km"] = None
        parts["_gas_error"] = str(e)[:120]
    parts["ghi_kwh_m2_day"] = solar.ghi(lat, lon)

    gas_km = parts.get("gas_pipeline_km")
    ghi_v = parts.get("ghi_kwh_m2_day")
    if gas_km is None and ghi_v is None:
        return [unknown(fid, "composite", "neither gas pipeline nor irradiance measurable", "index")]

    # Gas: 0 km -> 100, 50 km -> 0.
    gas_score = max(0.0, 100.0 - (gas_km / 50.0) * 100.0) if gas_km is not None else None
    # GHI: 2.5 kWh/m2/day -> 0, 7.0 -> 100.
    solar_score = max(0.0, min(100.0, (ghi_v - 2.5) / 4.5 * 100.0)) if ghi_v is not None else None

    weights, values = [], []
    if gas_score is not None:
        weights.append(0.65)
        values.append(gas_score)
    if solar_score is not None:
        weights.append(0.35)
        values.append(solar_score)
    index = sum(w * v for w, v in zip(weights, values, strict=True)) / sum(weights)

    tier = "B" if gas_score is not None else "C"
    return [Measurement(
        factor_id=fid, value=round(index, 1), unit="index_0_100", tier=tier, source="composite",
        raw={**parts, "gas_component": gas_score and round(gas_score, 1),
             "solar_component": solar_score and round(solar_score, 1)},
        notes=(
            f"Composite: gas pipeline {gas_km if gas_km is not None else 'not found'} km"
            f"{'' if gas_km is None else ' (65% weight)'}, GHI {ghi_v} kWh/m2/day (35% weight). "
            f"Wind and land-for-generation components not yet implemented — index is therefore "
            f"conservative. Solar/wind cannot firm a data center load; counted here only for a "
            f"hybrid or bridging strategy."
        ),
    )]


def measure(
    lat: float,
    lon: float,
    domains: list[str] | None = None,
    on_progress: Callable[[str, str], None] | None = None,
) -> list[Measurement]:
    """Run every adapter for the requested domains. Returns one entry per factor."""
    wanted = domains or list(DISPATCH)
    out: list[Measurement] = []

    for domain in wanted:
        for label, fn in DISPATCH.get(domain, []):
            if on_progress:
                on_progress(domain, label)
            try:
                out.extend(fn(lat, lon))
            except Exception as e:                      # an adapter bug, not a source failure
                out.append(unknown(
                    f"{domain}._adapter_{label}", "dispatcher",
                    f"adapter raised {type(e).__name__}: {e}",
                ))
                traceback.clear_frames(e.__traceback__) if e.__traceback__ else None

    # Every factor in scope must be represented, even if only as an unknown.
    seen = {m.factor_id for m in out}
    for fid, spec in load_factors().items():
        if spec["domain"] in wanted and fid not in seen:
            out.append(unknown(
                fid, "none",
                f"no adapter implemented; Tier C research required "
                f"(sources: {', '.join(spec.get('sources', [])[:3])})",
                spec.get("unit", ""),
            ))
    return out


def resolve_context(lat: float, lon: float) -> dict:
    return context.resolve(lat, lon)

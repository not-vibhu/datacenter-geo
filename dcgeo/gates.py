"""Gate implementations.

The `logic:` field in config/gates.yaml is documentation for humans. The executable
truth is here — evaluating strings from a config file would be both unsafe and
untestable. `validate_gate_coverage()` asserts the two stay in sync.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from .models import Analysis, GateResult, Measurement, Tier
from .registry import load_gates, load_profiles

GateFn = Callable[[Analysis, str, dict[str, Measurement], dict[str, Any]], GateResult]
_GATES: dict[str, GateFn] = {}


def gate(gate_id: str):
    def deco(fn: GateFn) -> GateFn:
        _GATES[gate_id] = fn
        return fn
    return deco


def _spec(gate_id: str) -> dict[str, Any]:
    for g in load_gates():
        if g["id"] == gate_id:
            return g
    raise KeyError(gate_id)


def _val(mm: dict[str, Measurement], fid: str) -> Any:
    m = mm.get(fid)
    return m.value if m else None


def _tier(mm: dict[str, Measurement], *fids: str) -> Tier:
    """Worst tier among the measurements a gate actually relied on."""
    order = ["A", "B", "C", "D", "unknown"]
    tiers = [mm[f].tier for f in fids if f in mm]
    if not tiers:
        return "unknown"
    return max(tiers, key=lambda t: order.index(t))


def _result(gate_id: str, outcome: str, reason: str, tier: Tier) -> GateResult:
    s = _spec(gate_id)
    return GateResult(
        gate_id=gate_id,
        name=s["name"],
        outcome=outcome,
        reason=reason,
        evidence_tier=tier,
        low_confidence=(outcome == "FAIL" and tier in ("C", "D", "unknown")),
        capped_score=s.get("capped_score_if_conditional") if outcome == "CONDITIONAL" else None,
        remediation_hint=s.get("remediation_hint"),
    )


# ── power ────────────────────────────────────────────────────────────────────

@gate("gate.power_path_exists")
def _power_path(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.power_path_exists"
    queue_yrs = _val(mm, "pwr.interconnect_queue_time")
    onsite = _val(mm, "pwr.onsite_generation_potential")
    headroom = _val(mm, "pwr.substation_headroom")
    tier = _tier(mm, "pwr.interconnect_queue_time", "pwr.onsite_generation_potential")

    years_available = ctx["target_year"] - ctx["current_year"]
    if queue_yrs is not None and queue_yrs > years_available:
        # Behind-the-meter generation is the escape hatch that many 2025-2026 US
        # projects are actually being built on.
        if onsite is None or onsite < 45:
            return _result(
                gid, "FAIL",
                f"Interconnection ~{queue_yrs} yr exceeds the {years_available} yr to target "
                f"{ctx['target_year']}, and on-site generation potential "
                f"({'unknown' if onsite is None else round(onsite)}) is insufficient to bridge it.",
                tier,
            )
        return _result(
            gid, "CONDITIONAL",
            f"Grid path ({queue_yrs} yr) misses target {ctx['target_year']}, but on-site "
            f"generation potential is {round(onsite)}/100 — viable only as a behind-the-meter build.",
            tier,
        )

    required_mva = ctx["target_load_mw"] * 1.15
    if headroom is None:
        return _result(
            gid, "CONDITIONAL",
            "Substation available capacity is unknown — the most common cause of late-stage "
            "project failure. Verify with the utility before committing capital.",
            _tier(mm, "pwr.substation_headroom"),
        )
    if headroom < required_mva:
        return _result(
            gid, "CONDITIONAL",
            f"Substation headroom {headroom} MVA is below the ~{required_mva:.0f} MVA needed "
            f"for {ctx['target_load_mw']} MW; a substation or transmission upgrade is required.",
            tier,
        )
    return _result(gid, "PASS", f"Queue {queue_yrs} yr and {headroom} MVA headroom clear the target.", tier)


# ── water ────────────────────────────────────────────────────────────────────

@gate("gate.water_viable")
def _water(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.water_viable"
    cooling = a.cooling_assumption
    tier = _tier(mm, "wtr.withdrawal_permitting", "wtr.basin_stress")

    if cooling == "air_cooled":
        return _result(gid, "PASS", "Air-cooled design assumed; water is not a gating constraint.", tier)

    permit = _val(mm, "wtr.withdrawal_permitting")
    if permit == "unavailable":
        return _result(gid, "FAIL", "No lawful pathway to the required water withdrawal.", tier)

    stress = _val(mm, "wtr.basin_stress")
    if stress is not None and stress > 0.8:
        return _result(
            gid, "CONDITIONAL",
            f"Baseline water stress {stress:.2f} is extremely high. An evaporative design here "
            f"carries severe political and permit risk; price an air-cooled or closed-loop alternative.",
            tier,
        )
    if permit == "severely_constrained":
        return _result(gid, "CONDITIONAL", "Withdrawal permitting is severely constrained in this basin.", tier)
    if stress is None and permit is None:
        return _result(gid, "CONDITIONAL", "Water availability and rights both unmeasured.", "unknown")
    return _result(gid, "PASS", f"Water viable for the assumed {cooling} design.", tier)


# ── hazard ───────────────────────────────────────────────────────────────────

@gate("gate.flood_exclusion")
def _flood(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.flood_exclusion"
    rp = _val(mm, "clm.flood_riverine")
    fb = _val(mm, "clm.flood_coastal")
    tier = _tier(mm, "clm.flood_riverine", "clm.flood_coastal")

    if rp is not None and rp <= 100:
        return _result(gid, "FAIL", f"Site intersects the {rp}-year floodplain. Lenders and insurers "
                                    f"apply this exclusion categorically.", tier)
    if fb is not None and fb < 0:
        return _result(gid, "FAIL", f"Projected 2050 storm tide exceeds site elevation "
                                    f"(freeboard {fb} m).", tier)
    if rp is not None and rp <= 500:
        return _result(gid, "CONDITIONAL", f"Within the {rp}-year floodplain; elevation and a local "
                                           f"flood study will be required for financing.", tier)
    if rp is None:
        return _result(gid, "CONDITIONAL", "Flood exposure unmeasured.", "unknown")
    return _result(gid, "PASS", f"Outside the 500-year floodplain (modeled return period {rp} yr).", tier)


@gate("gate.protected_exclusion")
def _protected(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.protected_exclusion"
    ov = _val(mm, "lnd.protected_overlap")
    tier = _tier(mm, "lnd.protected_overlap")
    if ov is None:
        return _result(gid, "CONDITIONAL", "Protected-area overlap unmeasured.", "unknown")
    if ov > 10:
        return _result(gid, "FAIL", f"{ov:.1f}% of the site overlaps protected or designated land.", tier)
    if ov > 0:
        return _result(gid, "CONDITIONAL", f"{ov:.1f}% protected-area overlap; reconfigure the site "
                                           f"boundary to eliminate it rather than seeking mitigation.", tier)
    return _result(gid, "PASS", "No protected-area overlap detected.", tier)


# ── land ─────────────────────────────────────────────────────────────────────

@gate("gate.land_sufficient")
def _land(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.land_sufficient"
    ha = _val(mm, "lnd.contiguous_area")
    tier = _tier(mm, "lnd.contiguous_area")
    req = ctx["land_min_ha"]
    typ = ctx["land_typical_ha"]
    if ha is None:
        return _result(gid, "CONDITIONAL", "Contiguous developable area unmeasured.", "unknown")
    if ha < req:
        return _result(gid, "FAIL", f"{ha:.0f} ha developable is below the {req} ha minimum for "
                                    f"profile '{profile}'.", tier)
    if ha < typ:
        return _result(gid, "CONDITIONAL", f"{ha:.0f} ha is workable but below the {typ} ha typical "
                                           f"footprint; expansion headroom is limited.", tier)
    return _result(gid, "PASS", f"{ha:.0f} ha contiguous developable area (computed upper bound).", tier)


@gate("gate.entitlement_path_exists")
def _entitlement(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.entitlement_path_exists"
    z = _val(mm, "lnd.zoning_status")
    tier = _tier(mm, "lnd.zoning_status")
    if z is None:
        return _result(gid, "CONDITIONAL", "Zoning status unmeasured.", "unknown")
    if z == "incompatible":
        return _result(gid, "FAIL", "Current zoning is incompatible with no rezoning pathway.", tier)
    if z in ("rezoning_contested", "rezoning_routine"):
        return _result(gid, "CONDITIONAL", f"Requires discretionary rezoning ({z}) — this converts an "
                                           f"engineering problem into a political one.", tier)
    return _result(gid, "PASS", f"Entitlement status: {z}.", tier)


# ── community & legal ────────────────────────────────────────────────────────

@gate("gate.no_active_moratorium")
def _moratorium(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.no_active_moratorium"
    o = _val(mm, "com.opposition_risk")
    tier = _tier(mm, "com.opposition_risk")
    if o is None:
        return _result(gid, "CONDITIONAL", "Local opposition status not researched.", "unknown")
    if o == "moratorium_active":
        return _result(gid, "FAIL", "An active data center moratorium is in force. Verify scope and "
                                    "expiry — many are time-limited or capped by megawatt.", tier)
    if o == "organized_opposition":
        return _result(gid, "CONDITIONAL", "Organized local opposition is present and has defeated or "
                                           "delayed comparable applications.", tier)
    return _result(gid, "PASS", f"Community status: {o}.", tier)


@gate("gate.compute_legally_deployable")
def _export(a: Analysis, profile: str, mm: dict[str, Measurement], ctx: dict) -> GateResult:
    gid = "gate.compute_legally_deployable"
    e = _val(mm, "reg.export_controls")
    tier = _tier(mm, "reg.export_controls")
    if e is None:
        return _result(gid, "CONDITIONAL", "Export control exposure not assessed.", "unknown")
    if e == "prohibited":
        return _result(gid, "FAIL", "Intended accelerators cannot lawfully be deployed at this location.", tier)
    if e in ("restricted_high_end", "license_uncertain"):
        return _result(gid, "CONDITIONAL", f"Export control status '{e}' — viable for domestically "
                                           f"available accelerators, uncertain for frontier hardware.", tier)
    return _result(gid, "PASS", f"Export control status: {e}.", tier)


# ── driver ───────────────────────────────────────────────────────────────────

def build_context(profile: str, analysis: Analysis) -> dict[str, Any]:
    p = load_profiles()["profiles"][profile]
    assumed = analysis.assumptions
    return {
        "current_year": datetime.now().year,
        "target_year": int(assumed.get("target_energization_year", p["target_energization_year"])),
        "target_load_mw": float(assumed.get("target_load_mw", p["target_it_load_mw"]["typical"])),
        "land_min_ha": float(p["land_requirement_ha"]["min"]),
        "land_typical_ha": float(p["land_requirement_ha"]["typical"]),
    }


def evaluate_gates(analysis: Analysis, profile: str) -> list[GateResult]:
    mm = analysis.measurement_map()
    ctx = build_context(profile, analysis)
    results: list[GateResult] = []
    for g in load_gates():
        if profile not in g.get("applies_to_profiles", []):
            continue
        fn = _GATES.get(g["id"])
        if fn is None:
            raise NotImplementedError(f"gate {g['id']} declared in config but not implemented")
        results.append(fn(analysis, profile, mm, ctx))
    return results


def validate_gate_coverage() -> list[str]:
    """Every gate in config must have an implementation, and vice versa."""
    declared = {g["id"] for g in load_gates()}
    implemented = set(_GATES)
    problems = [f"gate '{g}' declared in config but not implemented" for g in declared - implemented]
    problems += [f"gate '{g}' implemented but not declared in config" for g in implemented - declared]
    return problems

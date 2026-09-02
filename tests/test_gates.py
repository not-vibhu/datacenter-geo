"""Gate behavior. Gates are categorical and short-circuit — a weighted average will
otherwise average a deal-killer away."""
from dcgeo.gates import evaluate_gates
from dcgeo.models import Analysis, Measurement, Site
from dcgeo.scoring import apply_gates_to_scores, score_profile


def _analysis(ms, **kw):
    return Analysis(run_id="t", site=Site(site_id="t", name="t", centroid=(39.0, -77.0)),
                    measurements=ms, **kw)


def _gate(results, gate_id):
    return next(g for g in results if g.gate_id == gate_id)


def test_floodplain_is_a_hard_fail():
    a = _analysis([Measurement("clm.flood_riverine", 100, "years", "A", "fema_nfhl")])
    assert _gate(evaluate_gates(a, "hyperscale_training"), "gate.flood_exclusion").outcome == "FAIL"


def test_outside_500_year_floodplain_passes():
    a = _analysis([Measurement("clm.flood_riverine", 1000, "years", "A", "fema_nfhl")])
    assert _gate(evaluate_gates(a, "hyperscale_training"), "gate.flood_exclusion").outcome == "PASS"


def test_fatal_gate_overrides_a_high_score():
    """The whole reason gates exist."""
    ms = [
        Measurement("pwr.transmission_proximity", 0.5, "km", "A", "osm_overpass"),
        Measurement("lnd.slope", 0.5, "percent_slope", "A", "opentopography"),
        Measurement("clm.flood_riverine", 50, "years", "A", "fema_nfhl"),   # fatal
    ]
    a = _analysis(ms)
    a.profiles["hyperscale_training"] = score_profile(a, "hyperscale_training")
    a.gates = evaluate_gates(a, "hyperscale_training")
    apply_gates_to_scores(a)
    assert a.profiles["hyperscale_training"].verdict == "NO-GO"


def test_low_confidence_fail_is_marked_unverified():
    """We do not kill sites on the strength of a news article."""
    a = _analysis([Measurement("com.opposition_risk", "moratorium_active", "category",
                               "C", "local_news_media", source_url="https://example.com")])
    g = _gate(evaluate_gates(a, "hyperscale_training"), "gate.no_active_moratorium")
    assert g.outcome == "FAIL"
    assert g.low_confidence is True

    a.profiles["hyperscale_training"] = score_profile(a, "hyperscale_training")
    a.gates = [g]
    apply_gates_to_scores(a)
    assert a.profiles["hyperscale_training"].verdict == "NO-GO (unverified)"


def test_air_cooled_bypasses_the_water_gate():
    a = _analysis([Measurement("wtr.basin_stress", 0.95, "ratio", "A", "wri_aqueduct_40")],
                  cooling_assumption="air_cooled")
    assert _gate(evaluate_gates(a, "hyperscale_training"), "gate.water_viable").outcome == "PASS"


def test_high_water_stress_is_conditional_for_evaporative_designs():
    a = _analysis([Measurement("wtr.basin_stress", 0.95, "ratio", "A", "wri_aqueduct_40")],
                  cooling_assumption="evaporative")
    assert _gate(evaluate_gates(a, "hyperscale_training"), "gate.water_viable").outcome == "CONDITIONAL"


def test_onsite_generation_rescues_a_long_interconnection_queue():
    """The behind-the-meter escape hatch many 2025-2026 US projects are built on."""
    slow_only = _analysis([Measurement("pwr.interconnect_queue_time", 9, "years", "B", "iso_queues")])
    assert _gate(evaluate_gates(slow_only, "hyperscale_training"),
                 "gate.power_path_exists").outcome == "FAIL"

    with_gas = _analysis([
        Measurement("pwr.interconnect_queue_time", 9, "years", "B", "iso_queues"),
        Measurement("pwr.onsite_generation_potential", 80, "index_0_100", "B", "composite"),
    ])
    assert _gate(evaluate_gates(with_gas, "hyperscale_training"),
                 "gate.power_path_exists").outcome == "CONDITIONAL"


def test_land_gate_is_profile_sensitive():
    """5 ha is fatal for a training campus and fine for an edge site."""
    a = _analysis([Measurement("lnd.contiguous_area", 5.0, "hectares", "B", "osm_overpass")])
    assert _gate(evaluate_gates(a, "hyperscale_training"), "gate.land_sufficient").outcome == "FAIL"
    assert _gate(evaluate_gates(a, "inference_edge"), "gate.land_sufficient").outcome != "FAIL"


def test_conditional_gate_caps_but_does_not_kill():
    ms = [
        Measurement("pwr.transmission_proximity", 0.2, "km", "A", "osm_overpass"),
        Measurement("lnd.slope", 0.2, "percent_slope", "A", "opentopography"),
        Measurement("lnd.zoning_status", "rezoning_contested", "category", "B", "us_county_gis"),
    ]
    a = _analysis(ms)
    a.profiles["hyperscale_training"] = score_profile(a, "hyperscale_training")
    a.gates = [g for g in evaluate_gates(a, "hyperscale_training")
               if g.gate_id == "gate.entitlement_path_exists"]
    apply_gates_to_scores(a)
    ps = a.profiles["hyperscale_training"]
    assert ps.verdict != "NO-GO"
    assert ps.score <= 72

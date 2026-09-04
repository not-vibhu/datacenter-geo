"""The diligence layer must never turn an absence of evidence into a decision."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dcgeo import diligence
from dcgeo.compare import compare
from dcgeo.models import Analysis, Measurement, Site
from dcgeo.provenance import annotate, evidence_weight, freshness_of
from dcgeo.scoring import score_profile

PROFILE = "hyperscale_training"


def _site(name: str = "Test Site") -> Site:
    return Site(site_id="s1", name=name, centroid=(39.0, -77.5), country="United States")


def _m(fid: str, value, tier="A", source="osm_overpass", retrieved=None, **kw) -> Measurement:
    return Measurement(
        factor_id=fid, value=value, unit="", tier=tier, source=source,
        retrieved=retrieved or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **kw,
    )


def _scored(measurements: list[Measurement]) -> Analysis:
    a = Analysis(run_id="run_test", site=_site(), measurements=measurements)
    a.profiles[PROFILE] = score_profile(a, PROFILE)
    return a


# ── provenance ───────────────────────────────────────────────────────────────

def test_age_past_twice_the_ttl_is_stale_and_discounts_confidence():
    old = (datetime.now(UTC) - timedelta(days=400)).isoformat().replace("+00:00", "Z")
    fresh_m = _m("pwr.transmission_proximity", 1.0)
    stale_m = _m("pwr.transmission_proximity", 1.0, retrieved=old)

    assert freshness_of(fresh_m.source, fresh_m.retrieved)[0] == "fresh"
    assert freshness_of(stale_m.source, stale_m.retrieved)[0] == "stale"
    # Same tier, same value, same source — only the date differs.
    assert evidence_weight(stale_m) < evidence_weight(fresh_m)


def test_stale_tier_a_reports_lower_confidence_than_fresh_tier_a():
    old = (datetime.now(UTC) - timedelta(days=800)).isoformat().replace("+00:00", "Z")
    fresh = _scored([_m("pwr.transmission_proximity", 1.0)])
    stale = _scored([_m("pwr.transmission_proximity", 1.0, retrieved=old)])
    assert stale.profiles[PROFILE].confidence < fresh.profiles[PROFILE].confidence
    assert stale.profiles[PROFILE].band > fresh.profiles[PROFILE].band


def test_unknown_measurement_has_zero_datapoint_confidence():
    m = Measurement(factor_id="pwr.substation_headroom", value=None, unit="MVA",
                    tier="A", source="utility_planning_docs", unknown_reason="no adapter")
    ann = annotate(m)
    assert ann["known"] is False
    assert ann["confidence"] == 0.0
    assert ann["unknown_reason"] == "no adapter"


def test_every_scored_factor_carries_its_provenance():
    a = _scored([_m("pwr.transmission_proximity", 1.0, source="osm_overpass")])
    fs = next(f for f in a.profiles[PROFILE].factor_scores
              if f.factor_id == "pwr.transmission_proximity")
    assert fs.source == "osm_overpass"
    assert fs.retrieved is not None
    assert fs.freshness == "fresh"


# ── sensitivity ──────────────────────────────────────────────────────────────

def test_sensitivity_agrees_with_the_real_scorer():
    """The counterfactual must run through score_profile, not a parallel formula."""
    a = _scored([_m("pwr.transmission_proximity", 1.0),
                 _m("lnd.contiguous_area", 500.0)])
    sw = {s.factor_id: s for s in diligence.sensitivity(a, PROFILE)}
    s = sw["pwr.transmission_proximity"]
    forced = score_profile(a, PROFILE, None, counterfactual={"pwr.transmission_proximity": (100.0, "A")})
    assert s.score_if_best == pytest.approx(forced.score)
    assert s.swing == pytest.approx(s.score_if_best - s.score_if_worst)


def test_swing_is_never_negative():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    assert all(s.swing >= 0 for s in diligence.sensitivity(a, PROFILE))


def test_unmeasured_gate_factor_is_flagged_gate_critical():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    sw = {s.factor_id: s for s in diligence.sensitivity(a, PROFILE)}
    # substation headroom feeds gate.power_path_exists and is not measured here
    assert sw["pwr.substation_headroom"].gate_critical is True
    assert sw["pwr.transmission_proximity"].gate_critical is False


# ── blockers ─────────────────────────────────────────────────────────────────

def test_a_dark_domain_is_one_blocker_not_seven():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    b = diligence.build_brief(a, PROFILE)
    blackouts = [x for x in b.blockers if x.kind == "domain_blackout"]
    reg = [x for x in blackouts if x.domain == "regulatory"]
    assert len(reg) == 1
    # and the individual regulatory unknowns are absorbed into it
    assert not [x for x in b.blockers
                if x.kind == "unknown_material" and x.domain == "regulatory"]


def test_dark_domain_blocker_states_it_left_the_score():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    b = diligence.build_brief(a, PROFILE)
    reg = next(x for x in b.blockers if x.blocker_id == "blk.blackout.regulatory")
    assert "excluded from the score" in reg.why
    assert b.domain_coverage["regulatory"]["in_score"] is False


def test_every_blocker_names_a_counterparty():
    a = _scored([_m("pwr.transmission_proximity", 1.0), _m("lnd.slope", 2.0)])
    b = diligence.build_brief(a, PROFILE)
    assert b.blockers
    for x in b.blockers:
        assert x.owner and "Not routed" not in x.owner, x.blocker_id
        assert x.resolve


def test_verification_routing_is_jurisdictional():
    us = diligence.verification_for("pwr.substation_headroom", "United States")
    india = diligence.verification_for("pwr.substation_headroom", "India")
    assert "DISCOM" in india["owner"]
    assert us["owner"] != india["owner"]


# ── the decision ─────────────────────────────────────────────────────────────

def test_thin_evidence_yields_not_proven_never_a_recommendation():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    b = diligence.build_brief(a, PROFILE)
    assert b.decision == diligence.NOT_PROVEN
    assert b.can_answer_profitability is False
    assert "unanswerable" in b.headline or "Not yet" in b.headline


def test_profitability_is_refused_until_its_inputs_exist():
    a = _scored([_m("lnd.contiguous_area", 500.0)])
    b = diligence.build_brief(a, PROFILE)
    assert b.can_answer_profitability is False
    assert "cost inputs are unmeasured" in b.profitability_basis


def test_verification_queue_puts_gate_critical_first():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    b = diligence.build_brief(a, PROFILE)
    gate_ranks = [v.rank for v in b.verification_queue if v.gate_critical]
    other_ranks = [v.rank for v in b.verification_queue if not v.gate_critical]
    assert gate_ranks
    if other_ranks:
        assert max(gate_ranks) < min(other_ranks)


def test_queue_items_are_actionable():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    for v in diligence.build_brief(a, PROFILE).verification_queue:
        assert v.question and v.owner and v.artifact
        assert v.points_at_risk > 0


def test_briefs_cover_every_scored_profile_and_serialize():
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    a.profiles["inference_edge"] = score_profile(a, "inference_edge")
    bs = diligence.briefs(a)
    assert set(bs) == {PROFILE, "inference_edge"}
    assert bs[PROFILE].to_dict()["decision"] == diligence.NOT_PROVEN


def test_the_brief_is_not_persisted_into_the_evidence_ledger():
    """Derived output in the ledger would go stale while still looking authoritative."""
    a = _scored([_m("pwr.transmission_proximity", 1.0)])
    assert "diligence" not in a.to_dict()


# ── comparison ───────────────────────────────────────────────────────────────

def _two_sites() -> list[Analysis]:
    a = Analysis(run_id="run_a", site=_site("A"),
                 measurements=[_m("pwr.transmission_proximity", 0.5),
                               _m("lnd.contiguous_area", 900.0)])
    b = Analysis(run_id="run_b", site=_site("B"),
                 measurements=[_m("pwr.transmission_proximity", 40.0),
                               _m("lnd.contiguous_area", 900.0)])
    for x in (a, b):
        x.profiles[PROFILE] = score_profile(x, PROFILE)
    return [a, b]


def test_comparison_explains_the_gap_not_just_the_rank():
    c = compare(_two_sites(), PROFILE)
    top = c.sites[0]
    assert top.wins, "a leading site must say what it wins on"
    assert top.wins[0].factor_id == "pwr.transmission_proximity"
    assert top.wins[0].delta > 0


def test_overlapping_bands_refuse_to_rank():
    c = compare(_two_sites(), PROFILE)
    if not c.separable:
        assert "not supported by the evidence" in c.separability_note
        assert c.overlapping_pairs


def test_factors_measured_nowhere_are_reported_as_shared_blind_spots():
    c = compare(_two_sites(), PROFILE)
    ids = {b["factor_id"] for b in c.shared_blind_spots}
    assert "pwr.substation_headroom" in ids
    assert c.comparable_fraction < 1.0


def test_a_factor_only_one_site_measured_is_not_an_edge():
    """You cannot win on a factor the other site never measured."""
    sites = _two_sites()
    sites[0].measurements.append(_m("wtr.basin_stress", 0.1))
    sites[0].profiles[PROFILE] = score_profile(sites[0], PROFILE)
    c = compare(sites, PROFILE)
    for s in c.sites:
        assert "wtr.basin_stress" not in {e.factor_id for e in s.wins + s.loses}

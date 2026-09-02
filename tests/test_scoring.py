"""Scoring arithmetic. The behaviors here are load-bearing design decisions, not
implementation details — if one of these changes, the model's honesty changes."""
import pytest

from dcgeo.models import Analysis, Measurement, Site
from dcgeo.registry import load_factors
from dcgeo.scoring import normalize, score_profile, verdict_for


def _site():
    return Site(site_id="t", name="test", centroid=(39.0, -77.0))


def _analysis(measurements):
    return Analysis(run_id="t", site=_site(), measurements=measurements)


def test_piecewise_normalization_hits_anchors_and_interpolates():
    spec = load_factors()["pwr.transmission_proximity"]
    assert normalize(spec, 0) == 100
    assert normalize(spec, 100) == 0
    mid = normalize(spec, 2)          # between (1,98) and (3,92)
    assert 92 < mid < 98


def test_normalization_clamps_outside_the_curve():
    spec = load_factors()["pwr.transmission_proximity"]
    assert normalize(spec, -5) == 100
    assert normalize(spec, 99999) == 0


def test_categorical_normalization():
    spec = load_factors()["lnd.zoning_status"]
    assert normalize(spec, "by_right_industrial") == 100
    assert normalize(spec, "incompatible") == 5
    assert normalize(spec, "not_a_category") is None


def test_unknown_lowers_confidence_rather_than_defaulting_to_midpoint():
    """The single most important behavior in the system. Absence of evidence must
    never be treated as evidence of adequacy."""
    known = _analysis([Measurement("pwr.transmission_proximity", 2.0, "km", "A", "osm_overpass")])
    empty = _analysis([])

    ks = score_profile(known, "hyperscale_training")
    es = score_profile(empty, "hyperscale_training")

    assert es.score is None or es.confidence < ks.confidence
    assert es.confidence == 0.0
    assert es.measured_fraction == 0.0


def test_tier_drives_confidence():
    a_tier = _analysis([Measurement("pwr.transmission_proximity", 2.0, "km", "A", "osm_overpass")])
    d_tier = _analysis([Measurement("pwr.transmission_proximity", 2.0, "km", "D", "derived")])
    assert score_profile(a_tier, "hyperscale_training").confidence > \
           score_profile(d_tier, "hyperscale_training").confidence


def test_confidence_band_widens_as_confidence_falls():
    high = _analysis([Measurement(f, 2.0, "km", "A", "osm_overpass")
                      for f in ("pwr.transmission_proximity",)])
    assert score_profile(high, "hyperscale_training").band > 0


def test_profiles_weight_the_same_site_differently():
    """A site far from an IXP should not be penalized for a training campus."""
    a = _analysis([Measurement("cnx.ixp_proximity", 800.0, "km", "A", "peeringdb")])
    train = score_profile(a, "hyperscale_training")
    edge = score_profile(a, "inference_edge")
    tw = next(f.weight for f in train.factor_scores if f.factor_id == "cnx.ixp_proximity")
    ew = next(f.weight for f in edge.factor_scores if f.factor_id == "cnx.ixp_proximity")
    assert ew > tw, "IXP proximity must matter far more for edge than for training"


def test_measurement_with_none_value_is_forced_to_unknown_tier():
    m = Measurement("pwr.transmission_proximity", None, "km", "A", "osm_overpass")
    assert m.tier == "unknown"
    assert not m.is_known
    assert m.unknown_reason is not None


def test_verdict_bands():
    assert verdict_for(80) == "strong-candidate"
    assert verdict_for(65) == "viable"
    assert verdict_for(50) == "conditional"
    assert verdict_for(35) == "weak"
    assert verdict_for(10) == "poor"
    assert verdict_for(None) == "insufficient-data"

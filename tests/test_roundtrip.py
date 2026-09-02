"""A saved analysis must round-trip losslessly.

Regression test: `add-measurement` previously loaded an analysis without its
profiles and gates, then saved it — silently destroying the scoring results of
any run it touched.
"""
import json

from dcgeo.cli import _load, _save
from dcgeo.gates import evaluate_gates
from dcgeo.models import Analysis, Measurement, Site
from dcgeo.scoring import score_profile


def test_analysis_roundtrips_with_profiles_and_gates(tmp_path, monkeypatch):
    from dcgeo import cli
    monkeypatch.setattr(cli, "RUNS", tmp_path)

    a = Analysis(
        run_id="run_9999",
        site=Site(site_id="t", name="t", centroid=(39.0, -77.0)),
        measurements=[
            Measurement("pwr.transmission_proximity", 2.0, "km", "A", "osm_overpass"),
            Measurement("clm.flood_riverine", 1000, "years", "A", "fema_nfhl"),
        ],
    )
    a.profiles["hyperscale_training"] = score_profile(a, "hyperscale_training")
    a.gates = evaluate_gates(a, "hyperscale_training")
    a.red_team = ["a finding"]
    _save(a)

    b = _load("run_9999")
    assert list(b.profiles) == list(a.profiles)
    assert len(b.gates) == len(a.gates)
    assert b.red_team == a.red_team
    assert b.profiles["hyperscale_training"].score == a.profiles["hyperscale_training"].score
    assert len(b.profiles["hyperscale_training"].factor_scores) == \
           len(a.profiles["hyperscale_training"].factor_scores)

    # And a second save must not degrade it further.
    _save(b)
    c = _load("run_9999")
    assert c.profiles["hyperscale_training"].score == a.profiles["hyperscale_training"].score
    assert len(c.gates) == len(a.gates)

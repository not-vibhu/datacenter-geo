import json
from pathlib import Path

import httpx
import pytest

from scripts import build_atlas_data
from scripts.build_atlas_data import build, facilities_snapshot, overlays_snapshot, proximity_grid


def test_atlas_is_reproducible_and_every_feature_has_a_source():
    payload = build()
    committed = json.loads((Path(__file__).parents[1] / "site/data/atlas.json").read_text())
    assert payload == committed
    for facility in payload["facilities"]:
        assert facility["source_url"].startswith("https://")
        assert facility["retrieved"]
        assert facility["coordinate_precision"]
    ids = {f["id"] for f in payload["overlays"]["features"]}
    assert all(c["nearest_id"] in ids for c in payload["proximity"]["cells"])
    assert all(0 <= c["intensity"] <= 1 for c in payload["proximity"]["cells"])


def test_unlocated_facilities_are_not_silently_mapped_to_zero():
    records = [{"id": 1, "name": "Missing point", "country": "IN", "status": "ok", "latitude": None, "longitude": None}]
    result = facilities_snapshot({"data": records}, "2026-09-06T00:00:00Z")
    assert not result["facilities"]
    assert result["excluded_coordinates"] == 1


def test_an_incomplete_overpass_response_is_never_accepted_as_complete():
    with pytest.raises(ValueError, match="incomplete"):
        overlays_snapshot({"elements": [], "remark": "runtime timeout"}, "now")


def test_no_substations_produces_no_proximity_surface():
    assert proximity_grid({"features": []})["cells"] == []


def test_refresh_keeps_all_previous_snapshots_when_infrastructure_fails(tmp_path, monkeypatch):
    original = {"facilities.json": b'{"old":"facilities"}', "bhopal-osm.geojson": b'{"old":"overlays"}'}
    for name, contents in original.items():
        (tmp_path / name).write_bytes(contents)

    def respond(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": 1, "name": "Located facility",
                "country": "IN", "status": "ok", "latitude": 23.2, "longitude": 77.4}]})
        return httpx.Response(503, text="Source unavailable")

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(build_atlas_data, "SOURCE", tmp_path)
    monkeypatch.setattr(build_atlas_data.httpx, "Client", lambda **kwargs: client)
    with pytest.raises(ValueError, match="prior snapshot retained"):
        build_atlas_data.refresh()
    for name, contents in original.items():
        assert (tmp_path / name).read_bytes() == contents

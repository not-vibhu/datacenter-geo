import json

import pytest
from click.testing import CliRunner
from shapely.geometry import Point, shape

from dcgeo import cli as cli_module
from dcgeo.boundary import load_boundary
from dcgeo.cli import cli


@pytest.fixture
def boundary():
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [
        [[77.4, 23.2], [77.41, 23.2], [77.41, 23.21], [77.4, 23.21], [77.4, 23.2]],
        [[77.402, 23.202], [77.402, 23.204], [77.404, 23.204], [77.404, 23.202], [77.402, 23.202]],
    ]}, "properties": {"name": "Bhopal parcel"}}


def test_exact_boundary_and_holes_survive_cli_analysis(tmp_path, monkeypatch, boundary):
    path = tmp_path / "boundary.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [boundary]}))
    geometry, (lat, lon), name = load_boundary(path)
    assert geometry == boundary["geometry"]
    assert shape(geometry).contains(Point(lon, lat))
    assert name == "Bhopal parcel"
    monkeypatch.setattr(cli_module, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(cli_module.measure_mod, "resolve_context", lambda *_: {"country": "India"})
    monkeypatch.setattr(cli_module.measure_mod, "measure", lambda *_args, **_kw: [])
    result = CliRunner().invoke(cli, ["analyze", "--boundary", str(path), "--profile", "hyperscale_training"])
    assert result.exit_code == 0, result.output
    output = json.loads((tmp_path / "runs/run_0001/analysis.json").read_text())
    geojson = json.loads((tmp_path / "runs/run_0001/site.geojson").read_text())
    assert output["site"]["geometry"] == boundary["geometry"]
    assert geojson["features"][0]["geometry"] == boundary["geometry"]
    assert "not a polygon-wide" in result.output


@pytest.mark.parametrize("geometry", [
    {"type": "Point", "coordinates": [77, 23]},
    {"type": "Polygon", "coordinates": []},
    {"type": "Polygon", "coordinates": [[[77, 23], [78, 24], [78, 23], [77, 24], [77, 23]]]},
    {"type": "Polygon", "coordinates": [[[77, 23], [181, 23], [78, 24], [77, 23]]]},
    {"type": "Polygon", "coordinates": [[[77, 23], [78, 23], [78, 24], [77, 24]]]},
])
def test_invalid_boundary_fails_before_network(tmp_path, monkeypatch, geometry):
    path = tmp_path / "bad.geojson"
    path.write_text(json.dumps(geometry))
    def never_called(*_):
        pytest.fail("invalid input must fail before an API call")
    monkeypatch.setattr(cli_module.measure_mod, "resolve_context", never_called)
    result = CliRunner().invoke(cli, ["analyze", "--boundary", str(path)])
    assert result.exit_code != 0
    assert "invalid site input" in result.output


def test_boundary_and_coordinate_are_mutually_exclusive(tmp_path, boundary):
    path = tmp_path / "boundary.geojson"
    path.write_text(json.dumps(boundary))
    result = CliRunner().invoke(cli, ["analyze", "--at", "23,77", "--boundary", str(path)])
    assert result.exit_code != 0
    assert "exactly one" in result.output

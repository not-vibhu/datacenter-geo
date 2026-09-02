"""Adapter contract tests. No network — these check the invariants that keep one
bad endpoint from corrupting or aborting an analysis."""
from dcgeo.adapters import flood
from dcgeo.adapters.base import measured, unknown
from dcgeo.measure import DISPATCH
from dcgeo.registry import load_factors


def test_unknown_measurement_carries_a_reason_and_unknown_tier():
    m = unknown("pwr.transmission_proximity", "osm_overpass", "endpoint down", "km")
    assert m.value is None
    assert m.tier == "unknown"
    assert m.unknown_reason == "endpoint down"
    assert not m.is_known


def test_measured_records_geometry_when_given_coordinates():
    m = measured("lnd.slope", 2.0, "percent_slope", "A", "opentopography", lat=39.0, lon=-77.0)
    assert m.geometry_ref.startswith("geohash:")
    assert m.is_known


def test_flood_skips_the_network_entirely_outside_us_coverage():
    """Querying FEMA for a Chinese coordinate cannot succeed and costs a slow round
    trip per site, which is prohibitive when scanning a region."""
    m = flood.flood_return_period(41.02, 113.13)[0]
    assert m.value is None
    assert "non-US" in m.unknown_reason
    assert not flood._maybe_us(41.02, 113.13)
    assert flood._maybe_us(39.04, -77.49)


def test_coastal_adapter_returns_unknown_rather_than_guessing():
    m = flood.coastal_exposure(39.0, -77.0)[0]
    assert m.value is None
    assert "not implemented" in m.unknown_reason


def test_every_dispatch_domain_is_a_real_domain():
    domains = {s["domain"] for s in load_factors().values()}
    assert set(DISPATCH) <= domains


def test_terrain_declares_a_dataset_preference_order():
    """The public OpenTopoData instance does not serve Copernicus GLO-30. Assuming a
    dataset name that isn't hosted silently zeroed out lnd.slope on every run."""
    from dcgeo.adapters import terrain
    assert "copernicus30m" not in terrain.DATASETS
    assert terrain.DATASETS[0] == "mapzen"
    assert len(terrain.DATASETS) >= 2, "need a fallback for regions one DEM misses"


def test_measure_bounds_every_adapter_and_never_hangs():
    """A stalled endpoint must degrade to `unknown`, not stall the whole analysis.
    One such hang cost a 28-minute stall on a single site during validation."""
    import time

    from dcgeo import measure as measure_mod

    def stalls(lat, lon):
        time.sleep(30)
        return []

    original = measure_mod.DISPATCH.copy()
    original_timeout = measure_mod.ADAPTER_TIMEOUT_S
    try:
        measure_mod.DISPATCH = {"power": [("stalls", stalls)]}
        measure_mod.ADAPTER_TIMEOUT_S = 0.5
        t = time.time()
        ms = measure_mod.measure(39.0, -77.0, ["power"])
        assert time.time() - t < 10, "measure() did not honor the adapter ceiling"
        stalled = [m for m in ms if m.source == "dispatcher"]
        assert stalled and "ceiling" in stalled[0].unknown_reason
    finally:
        measure_mod.DISPATCH = original
        measure_mod.ADAPTER_TIMEOUT_S = original_timeout

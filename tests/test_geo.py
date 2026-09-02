import math
from dcgeo.geo import bbox_around, geohash, haversine_km, parse_latlon, tile_region, wet_bulb_stull


def test_haversine_against_known_distance():
    # Ashburn VA -> Abilene TX, ~2131 km
    d = haversine_km((39.0437, -77.4875), (32.4487, -99.7331))
    assert 2100 < d < 2160


def test_wet_bulb_is_below_dry_bulb_and_converges_at_saturation():
    assert wet_bulb_stull(35, 40) < 35
    assert abs(wet_bulb_stull(25, 100) - 25) < 1.0


def test_wet_bulb_matches_published_value():
    # 35 C at 40% RH is ~24.5 C wet bulb
    assert 24.0 < wet_bulb_stull(35, 40) < 25.0


def test_geohash_is_stable_and_precision_scales():
    assert geohash(39.0437, -77.4875) == geohash(39.0437, -77.4875)
    assert geohash(39.0437, -77.4875, 5) == geohash(39.0437, -77.4875, 7)[:5]


def test_bbox_is_centered_and_clamped():
    s, w, n, e = bbox_around(39.0, -77.0, 10)
    assert s < 39.0 < n and w < -77.0 < e
    assert bbox_around(89.9, 0, 500)[2] <= 90.0


def test_parse_latlon_accepts_both_separators_and_rejects_bad_input():
    assert parse_latlon("39.0437,-77.4875") == (39.0437, -77.4875)
    assert parse_latlon("39.0437 -77.4875") == (39.0437, -77.4875)
    for bad in ("garbage", "91,0", "0,181"):
        try:
            parse_latlon(bad)
            assert False, f"should have rejected {bad}"
        except ValueError:
            pass


def test_tiling_covers_the_box():
    tiles = list(tile_region(39.0, -77.5, 39.5, -77.0, 10))
    assert len(tiles) > 10
    assert all(39.0 <= la <= 39.5 and -77.5 <= lo <= -77.0 for la, lo in tiles)

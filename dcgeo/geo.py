"""Geodesy helpers. Small and dependency-light on purpose."""
from __future__ import annotations

import math
from typing import Iterable

EARTH_R_KM = 6371.0088


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between (lat, lon) pairs."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(h))


def bbox_around(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) bounding box. Clamped at the poles."""
    dlat = radius_km / 111.32
    coslat = max(math.cos(math.radians(lat)), 1e-6)
    dlon = radius_km / (111.32 * coslat)
    return (
        max(lat - dlat, -90.0),
        max(lon - dlon, -180.0),
        min(lat + dlat, 90.0),
        min(lon + dlon, 180.0),
    )


def geohash(lat: float, lon: float, precision: int = 7) -> str:
    """Standard geohash. Used as the cache key for location-scoped measurements.

    Precision 7 is ~150 m, which is the right granularity: two analyses of the same
    site should share cached measurements, two genuinely different sites should not.
    """
    b32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_r, lon_r = [-90.0, 90.0], [-180.0, 180.0]
    out, bit, ch, even = [], 0, 0, True
    while len(out) < precision:
        if even:
            mid = sum(lon_r) / 2
            if lon > mid:
                ch = (ch << 1) | 1
                lon_r[0] = mid
            else:
                ch <<= 1
                lon_r[1] = mid
        else:
            mid = sum(lat_r) / 2
            if lat > mid:
                ch = (ch << 1) | 1
                lat_r[0] = mid
            else:
                ch <<= 1
                lat_r[1] = mid
        even = not even
        bit += 1
        if bit == 5:
            out.append(b32[ch])
            bit, ch = 0, 0
    return "".join(out)


def parse_latlon(text: str) -> tuple[float, float]:
    """Parse '39.0437,-77.4875' or '39.0437 -77.4875'."""
    parts = [p for p in text.replace(",", " ").split() if p]
    if len(parts) != 2:
        raise ValueError(f"expected 'lat,lon', got {text!r}")
    lat, lon = float(parts[0]), float(parts[1])
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"coordinates out of range: {lat},{lon}")
    return lat, lon


def tile_region(
    south: float, west: float, north: float, east: float, step_km: float = 10.0
) -> Iterable[tuple[float, float]]:
    """Yield tile centroids covering a bbox. The coarse pass of the Prospector."""
    dlat = step_km / 111.32
    lat = south + dlat / 2
    while lat < north:
        coslat = max(math.cos(math.radians(lat)), 1e-6)
        dlon = step_km / (111.32 * coslat)
        lon = west + dlon / 2
        while lon < east:
            yield (round(lat, 5), round(lon, 5))
            lon += dlon
        lat += dlat


def wet_bulb_stull(temp_c: float, rh_pct: float) -> float:
    """Stull (2011) wet-bulb approximation. Valid roughly -20..50 C, 5..99% RH.

    Accurate to about ±0.3 C over the range that matters for cooling design, which
    is well inside the uncertainty of everything else in this system.
    """
    rh = max(min(rh_pct, 100.0), 1.0)
    t = temp_c
    return (
        t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )

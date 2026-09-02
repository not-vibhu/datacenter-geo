"""Terrain — elevation and slope from OpenTopoData (Copernicus GLO-30, no key)."""
from __future__ import annotations

import math

from ..geo import bbox_around
from ..models import Measurement
from .base import SourceUnavailable, cached, http_get, measured, unknown

# NOTE: the PUBLIC OpenTopoData instance does not host Copernicus GLO-30 — that is
# only available on a self-hosted instance. Datasets below are in preference order
# and are what the public API actually serves.
#   mapzen   — global blended terrain (SRTM + ArcticDEM + EU-DEM + others), best coverage
#   srtm30m  — well-understood provenance, but voids above 60 deg latitude
#   aster30m — global fallback, noisier
OPENTOPODATA = "https://api.opentopodata.org/v1"
DATASETS = ["mapzen", "srtm30m", "aster30m"]
SOURCE = "opentopography"
GRID = 5          # 5x5 sample grid = 25 points; public API caps at 100 per request


def _sample_grid(lat: float, lon: float, radius_km: float) -> list[tuple[float, float]]:
    s, w, n, e = bbox_around(lat, lon, radius_km)
    return [
        (s + (n - s) * i / (GRID - 1), w + (e - w) * j / (GRID - 1))
        for i in range(GRID) for j in range(GRID)
    ]


def slope_stats(lat: float, lon: float, radius_km: float = 2.0) -> list[Measurement]:
    """lnd.slope — mean and p90 slope across the site, plus elevation for flood freeboard."""
    fid = "lnd.slope"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            pts = _sample_grid(lat, lon, radius_km)
            loc = "|".join(f"{a:.5f},{b:.5f}" for a, b in pts)
            hit, last = None, None
            for ds in DATASETS:
                try:
                    d = http_get(f"{OPENTOPODATA}/{ds}", params={"locations": loc}, timeout=60.0)
                except SourceUnavailable as e:
                    last = e
                    continue
                if d.get("status") != "OK":
                    last = SourceUnavailable(f"{ds}: {d.get('error')}")
                    continue
                # A dataset can return OK with all-null elevations outside its footprint.
                if all(r.get("elevation") is None for r in d.get("results", [])):
                    last = SourceUnavailable(f"{ds}: no coverage at this location")
                    continue
                d["_dataset"] = ds
                hit = d
                break
            if hit is None:
                raise SourceUnavailable(f"no DEM coverage from {DATASETS}: {last}")
            store(hit)

        dataset = hit.get("_dataset", "unknown")
        results = hit.get("results", [])
        elevs = [r.get("elevation") for r in results]
        if any(e is None for e in elevs) or len(elevs) < GRID * GRID:
            return [unknown(fid, SOURCE, "incomplete DEM coverage at this location", "percent")]

        grid = [elevs[i * GRID:(i + 1) * GRID] for i in range(GRID)]
        s, w, n, e = bbox_around(lat, lon, radius_km)
        dy_m = (n - s) / (GRID - 1) * 111_320
        dx_m = (e - w) / (GRID - 1) * 111_320 * math.cos(math.radians(lat))

        slopes = []
        for i in range(GRID - 1):
            for j in range(GRID - 1):
                dz_y = abs(grid[i + 1][j] - grid[i][j])
                dz_x = abs(grid[i][j + 1] - grid[i][j])
                slopes.append(math.hypot(dz_x / max(dx_m, 1), dz_y / max(dy_m, 1)) * 100)

        slopes.sort()
        mean_slope = sum(slopes) / len(slopes)
        p90 = slopes[int(len(slopes) * 0.9)]
        mean_elev = sum(elevs) / len(elevs)

        return [measured(
            fid, round(mean_slope, 2), "percent_slope", "A", SOURCE, lat=lat, lon=lon,
            source_url="https://www.opentopodata.org/datasets/copernicus/",
            raw={"dem_dataset": dataset,
                 "p90_slope_pct": round(p90, 2), "mean_elevation_m": round(mean_elev, 1),
                 "min_elevation_m": round(min(elevs), 1), "max_elevation_m": round(max(elevs), 1),
                 "relief_m": round(max(elevs) - min(elevs), 1), "sample_points": len(elevs),
                 "sample_radius_km": radius_km},
            notes=(f"{dataset} DEM, {GRID}x{GRID} grid over {radius_km} km. Mean slope "
                   f"{mean_slope:.1f}%, p90 {p90:.1f}%, relief {max(elevs)-min(elevs):.0f} m. "
                   f"Below 2% is essentially free; earthwork cost rises roughly quadratically "
                   f"above that for a large flat-pad campus."),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "percent")]


def elevation_m(lat: float, lon: float) -> float | None:
    """Point elevation. Used for coastal freeboard."""
    for ds in DATASETS:
        try:
            d = http_get(f"{OPENTOPODATA}/{ds}", params={"locations": f"{lat:.5f},{lon:.5f}"},
                         timeout=30.0)
            v = d["results"][0]["elevation"]
            if v is not None:
                return v
        except (SourceUnavailable, KeyError, IndexError):
            continue
    return None

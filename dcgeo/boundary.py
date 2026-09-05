"""Validate a WGS84 site boundary without simplifying or replacing its geometry."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from shapely.validation import explain_validity


def load_boundary(path: Path) -> tuple[dict[str, Any], tuple[float, float], str | None]:
    """Return exact geometry, an interior (lat, lon) reference point, and a name.

    Accept one Polygon/MultiPolygon, Feature, or single-feature collection. A
    collection of separate sites must be analyzed separately. No repair is done:
    guessing the intended outline would change the land the user selected.
    """
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("boundary file exceeds the 2 MB limit")
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("expected a GeoJSON object")
    if raw.get("crs"):
        raise ValueError("use WGS84 longitude/latitude GeoJSON without a custom CRS")
    if raw.get("type") == "FeatureCollection":
        features = raw.get("features", [])
        if not isinstance(features, list) or len(features) != 1:
            raise ValueError("analyze one boundary at a time; export a single feature")
        raw = features[0]
    if not isinstance(raw, dict):
        raise ValueError("expected a GeoJSON Feature or geometry")
    properties = raw.get("properties") or {}
    geometry = raw.get("geometry") if raw.get("type") == "Feature" else raw
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("boundary must be a Polygon or MultiPolygon")
    if geometry.get("crs") or raw.get("crs"):
        raise ValueError("use WGS84 longitude/latitude GeoJSON without a custom CRS")
    polygons = [geometry.get("coordinates")] if geometry["type"] == "Polygon" else geometry.get("coordinates")
    if not isinstance(polygons, list) or not polygons:
        raise ValueError("boundary is empty")
    count = 0
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("polygon has no rings")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("each ring needs at least three vertices and must be closed")
            count += len(ring)
            for coord in ring:
                if not isinstance(coord, list) or len(coord) != 2:
                    raise ValueError("use 2D [longitude, latitude] coordinates")
                if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in coord):
                    raise ValueError("coordinates must be finite numbers")
                if not (-180 <= coord[0] <= 180 and -90 <= coord[1] <= 90):
                    raise ValueError("coordinates outside WGS84 longitude/latitude range")
    if count > 10000:
        raise ValueError("boundary exceeds 10,000 vertices")
    polygon = shape(geometry)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError(f"invalid boundary: {explain_validity(polygon)}")
    point = polygon.representative_point()
    name = properties.get("name") if isinstance(properties, dict) else None
    return geometry, (point.y, point.x), str(name) if name else None

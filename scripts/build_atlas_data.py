#!/usr/bin/env python3
"""Build the India map from attributed, committed snapshots; network is opt-in.

Run with --refresh to retrieve PeeringDB India facilities and bounded Bhopal OSM
features. The default build is offline and deterministic. These are map context,
never evidence of spare power capacity or parcel-level investment suitability.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dcgeo.geo import haversine_km, tile_region  # noqa: E402

SOURCE = ROOT / "data" / "atlas"
OUT = ROOT / "site" / "data"
BHOPAL_BBOX = [23.08, 77.18, 23.48, 77.65]  # pilot study extent, NOT an admin boundary
OSM_QUERIES = [
    '[out:json][timeout:120];('
    'way[power=line](23.08,77.18,23.48,77.65);'
    'way[power=substation](23.08,77.18,23.48,77.65);'
    'node[power=substation](23.08,77.18,23.48,77.65););out tags geom;',
    '[out:json][timeout:120];('
    'way[natural=water](23.08,77.18,23.48,77.65);'
    'way[landuse=industrial](23.08,77.18,23.48,77.65););out tags geom;',
]
OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def facilities_snapshot(raw: dict, retrieved: str) -> dict:
    # Explicit allowlist: no personal contact names, addresses, email or phone data.
    facilities, excluded = [], 0
    for record in raw["data"]:
        if record.get("country") != "IN" or record.get("status") != "ok":
            continue
        try:
            lat, lon = float(record["latitude"]), float(record["longitude"])
        except (KeyError, ValueError, TypeError):
            excluded += 1
            continue
        if not (6 <= lat <= 38 and 68 <= lon <= 98):
            excluded += 1
            continue
        facilities.append({
            "id": f"pdb-{record['id']}", "name": record["name"],
            "city": record.get("city", ""), "state": record.get("state", ""),
            "lat": lat, "lon": lon, "status": "listed", "kind": "facility",
            "source": "PeeringDB", "source_url": f"https://www.peeringdb.com/fac/{record['id']}",
            "retrieved": retrieved, "updated": record.get("updated"), "tier": "B",
            "coordinate_precision": "Directory point; facility footprint unverified",
            "notes": "Community-maintained facility listing. Operating status, IT capacity and spare capacity require operator verification.",
        })
    return {"retrieved": retrieved, "source_url": "https://www.peeringdb.com/api/fac?country=IN&depth=0",
            "license_url": "https://docs.peeringdb.com/gov/misc/2020-04-06_PeeringDB_Data_Ownership_Policy_Document_v1.0.pdf",
            "excluded_coordinates": excluded, "facilities": sorted(facilities, key=lambda f: f["id"])}


def overlays_snapshot(raw: dict, retrieved: str) -> dict:
    if raw.get("remark"):
        raise ValueError(f"Overpass returned incomplete data: {raw['remark']}")
    features, excluded = [], 0
    for element in raw["elements"]:
        tags = element.get("tags", {})
        category = (tags["power"] if tags.get("power") in ("line", "substation")
                    else "water" if tags.get("natural") == "water" else "industrial")
        geom = None
        if element["type"] == "node":
            geom = {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
        elif element["type"] == "way" and element.get("geometry"):
            coordinates = [[p["lon"], p["lat"]] for p in element["geometry"]]
            closed = len(coordinates) >= 4 and coordinates[0] == coordinates[-1]
            geom = {"type": "Polygon" if closed and category != "line" else "LineString",
                    "coordinates": [coordinates] if closed and category != "line" else coordinates}
        # Relations need proper multipolygon assembly; never invent a boundary.
        if not geom or not shape(geom).is_valid:
            excluded += 1
            continue
        reference = shape(geom).centroid
        features.append({
            "type": "Feature", "id": f"osm-{element['type']}-{element['id']}",
            "geometry": geom,
            "properties": {"category": category, "name": tags.get("name", tags.get("name:en", "")),
                           "reference_point": [reference.x, reference.y],
                           "voltage": tags.get("voltage"), "operator": tags.get("operator"),
                           "source": "OpenStreetMap", "tier": "B", "retrieved": retrieved,
                           "source_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}"},
        })
    return {"type": "FeatureCollection", "features": features, "retrieved": retrieved,
            "study_bbox": BHOPAL_BBOX, "excluded_geometries": excluded,
            "license": "ODbL-1.0", "source_url": "https://www.openstreetmap.org/copyright"}


def proximity_grid(overlays: dict) -> dict:
    """2 km sample spacing; straight-line distance to mapped substation centroid.

    This is a navigation aid, not the dcgeo scorer. The 10 km fade is an explicit
    display parameter. No capacity, tariff, hazard or land-availability inference.
    """
    substations = []
    for feature in overlays["features"]:
        if feature["properties"]["category"] == "substation":
            point = shape(feature["geometry"]).centroid
            substations.append((feature["id"], point.y, point.x))
    cells = []
    if substations:
        for lat, lon in tile_region(*BHOPAL_BBOX, step_km=2):
            distance, identifier = min(
                (haversine_km((lat, lon), (y, x)), fid) for fid, y, x in substations
            )
            cells.append({"lat": lat, "lon": lon, "distance_km": round(distance, 3),
                          "nearest_id": identifier,
                          "intensity": round(max(0, 1 - distance / 10), 4)})
    return {"cells": cells, "tier": "D", "spacing_km": 2, "fade_km": 10,
            "model": "max(0, 1 - nearest_mapped_substation_centroid_distance_km / 10)",
            "notes": "Geographic proximity only. Substation voltage and spare capacity are not verified. Coverage is limited to the Bhopal study extent; edges can be biased by missing features outside it."}


def build() -> dict:
    facilities = json.loads((SOURCE / "facilities.json").read_text())
    overlays = json.loads((SOURCE / "bhopal-osm.geojson").read_text())
    curated = json.loads((SOURCE / "curated.json").read_text())
    return {"version": 1, "facilities": facilities["facilities"] + curated["facilities"],
            "overlays": overlays, "proximity": proximity_grid(overlays),
            "meta": {"retrieved": facilities["retrieved"], "osm_retrieved": overlays["retrieved"],
                     "excluded_coordinates": facilities["excluded_coordinates"],
                     "excluded_geometries": overlays["excluded_geometries"],
                     "overlay_counts": dict(Counter(f["properties"]["category"] for f in overlays["features"])),
                     "facility_source": facilities["source_url"], "facility_license": facilities["license_url"],
                     "coverage": "India facility directory; Bhopal infrastructure pilot. Not a complete facility census."}}


def refresh() -> None:
    retrieved = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    with httpx.Client(timeout=60, headers={"User-Agent": "datacenter-geo/0.1 (github.com/not-vibhu/datacenter-geo)"}) as client:
        records = []
        # Explicit pagination avoids silently truncating a growing national inventory.
        while True:
            response = client.get("https://www.peeringdb.com/api/fac", params={
                "country": "IN", "depth": 0, "limit": 250, "skip": len(records),
            })
            response.raise_for_status()
            page = response.json()["data"]
            if any(record["id"] in {r["id"] for r in records} for record in page):
                raise ValueError("PeeringDB pagination repeated records; previous snapshot retained")
            records.extend(page)
            if len(page) < 250:
                break
        facilities = facilities_snapshot({"data": records}, retrieved)
        elements = []
        for query in OSM_QUERIES:
            failures = []
            for endpoint in OVERPASS_ENDPOINTS:
                try:
                    response = client.post(endpoint, data={"data": query}, timeout=150)
                    response.raise_for_status()
                    result = response.json()
                    if result.get("remark"):
                        raise ValueError(result["remark"])
                    elements.extend(result["elements"])
                    break
                except (httpx.HTTPError, ValueError, KeyError) as error:
                    failures.append(f"{endpoint}: {error}")
            else:
                raise ValueError("All infrastructure sources failed; prior snapshot retained. "
                                 + "; ".join(failures))
        overlays = overlays_snapshot({"elements": elements}, retrieved)
    # Keep the previous snapshot if either source fails; never replace with an empty fallback.
    if not facilities["facilities"] or not overlays["features"]:
        raise ValueError("Empty source response; previous snapshots retained")
    write_json(SOURCE / "facilities.json", facilities)
    write_json(SOURCE / "bhopal-osm.geojson", overlays)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch new public source snapshots")
    args = parser.parse_args()
    if args.refresh:
        refresh()
    payload = build()
    write_json(OUT / "atlas.json", payload)
    print(f"Built India atlas: {len(payload['facilities'])} facilities, "
          f"{len(payload['overlays']['features'])} mapped features, "
          f"{len(payload['proximity']['cells'])} proximity samples")

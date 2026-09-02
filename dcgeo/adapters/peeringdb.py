"""PeeringDB — IXPs, facilities, carriers. Free, machine-readable, genuinely Tier A."""
from __future__ import annotations

from ..geo import haversine_km
from ..models import Measurement
from .base import SourceUnavailable, cached, http_get, measured, unknown

API = "https://www.peeringdb.com/api"
SOURCE = "peeringdb"


def _facilities_near(lat: float, lon: float, box_deg: float = 6.0) -> list[dict]:
    """PeeringDB has no radius search, so fetch a bounding box of facilities."""
    hit, store = cached("cnx._fac", SOURCE, lat, lon, {"box": box_deg})
    if hit is not None:
        return hit.get("data", [])
    data = http_get(f"{API}/fac", params={
        "latitude__gte": lat - box_deg, "latitude__lte": lat + box_deg,
        "longitude__gte": lon - box_deg, "longitude__lte": lon + box_deg,
        "limit": 800,
    }, timeout=60.0)
    store(data)
    return data.get("data", [])


def nearest_ixp(lat: float, lon: float) -> list[Measurement]:
    """cnx.ixp_proximity — distance to the nearest interconnection facility."""
    fid = "cnx.ixp_proximity"
    try:
        facs = _facilities_near(lat, lon)
        scored = []
        for f in facs:
            flat, flon = f.get("latitude"), f.get("longitude")
            if flat is None or flon is None:
                continue
            scored.append((haversine_km((lat, lon), (flat, flon)), f))
        if not scored:
            return [unknown(fid, SOURCE, "no PeeringDB facilities in the search box", "km")]
        scored.sort(key=lambda x: x[0])
        d, f = scored[0]
        within_100 = sum(1 for dd, _ in scored if dd <= 100)
        return [measured(
            fid, round(d, 2), "km", "A", SOURCE, lat=lat, lon=lon,
            source_url=f"https://www.peeringdb.com/fac/{f.get('id')}",
            raw={"facility": f.get("name"), "city": f.get("city"), "country": f.get("country"),
                 "facilities_within_100km": within_100,
                 "nearest_five": [{"name": g.get("name"), "km": round(dd, 1)} for dd, g in scored[:5]]},
            notes=(f"Nearest interconnection facility '{f.get('name')}' at {d:.1f} km; "
                   f"{within_100} facilities within 100 km. Weight this near zero for a training "
                   f"campus — over-weighting it biases site selection toward expensive metro land."),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "km")]


def carrier_count(lat: float, lon: float, radius_km: float = 50.0) -> list[Measurement]:
    """cnx.carrier_count — distinct networks present at facilities within radius."""
    fid = "cnx.carrier_count"
    try:
        facs = _facilities_near(lat, lon)
        near = [f for f in facs
                if f.get("latitude") is not None
                and haversine_km((lat, lon), (f["latitude"], f["longitude"])) <= radius_km]
        if not near:
            return [unknown(fid, SOURCE,
                            f"no PeeringDB facilities within {radius_km:.0f} km. Absence here means "
                            f"no carrier-neutral facility, not that carriers cannot serve the site.",
                            "carriers")]
        # net_count is PeeringDB's count of networks present at the facility.
        counts = [f.get("net_count") or 0 for f in near]
        total = sum(counts)
        return [measured(
            fid, len(near) if total == 0 else min(total, 60), "count_carriers", "B", SOURCE,
            lat=lat, lon=lon, source_url="https://www.peeringdb.com/",
            raw={"facilities_within_radius": len(near), "network_presences": total,
                 "radius_km": radius_km},
            notes=(f"{total} network presences across {len(near)} facilities within {radius_km:.0f} km. "
                   f"Network presences at carrier-neutral facilities are a proxy for carrier "
                   f"availability, not a direct count of carriers able to serve this parcel."),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "carriers")]

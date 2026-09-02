"""Flood exposure.

FEMA NFHL is authoritative for the US and is what lenders and insurers actually use —
which is why gate.flood_exclusion is categorical rather than an engineering judgment.

Two endpoints are tried in order. FEMA's own hazards.fema.gov gateway is preferred but
is not reachable from all networks (it appears to be geo-restricted); the Esri-hosted
Living Atlas mirror of the same NFHL data is the fallback and is globally reachable.
Outside the US, coverage falls back to coarser global models and the tier drops.
"""
from __future__ import annotations

from ..models import Measurement
from .base import SourceUnavailable, cached, http_get, measured, unknown

SOURCE = "fema_nfhl"

# (url, timeout_seconds). The FEMA gateway gets a short timeout because on networks
# where it is blocked it hangs rather than refusing, and a 45 s hang per site makes
# region scanning unusable.
ENDPOINTS = [
    # Esri Living Atlas mirror of NFHL — globally reachable, public, no key.
    ("https://services5.arcgis.com/7weheFjxuNkGGiZi/arcgis/rest/services/"
     "USA_Flood_Hazard_Areas_view/FeatureServer/0/query", 60.0),
    # FEMA's own gateway — authoritative, but geo-restricted on some networks.
    ("https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query", 8.0),
]

# FEMA Special Flood Hazard Area zones = the 1% annual chance (100-year) floodplain.
SFHA_ZONES = {"A", "AE", "AH", "AO", "AR", "A99", "V", "VE"}

# Generous bounding box for NFHL coverage (CONUS + AK + HI + PR). Points outside it
# cannot have FEMA coverage, so querying wastes a slow round trip per site — which
# matters a lot when scanning regions.
US_BBOX = (17.5, -170.0, 72.0, -64.0)      # (south, west, north, east)


def _maybe_us(lat: float, lon: float) -> bool:
    s, w, n, e = US_BBOX
    return s <= lat <= n and w <= lon <= e


def _query(lat: float, lon: float) -> dict:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
        "returnGeometry": "false",
        "f": "json",
    }
    last: Exception | None = None
    for url, timeout in ENDPOINTS:
        try:
            d = http_get(url, params=params, timeout=timeout)
            if "error" in d:
                last = SourceUnavailable(f"{url}: {d['error'].get('message')}")
                continue
            return d
        except SourceUnavailable as e:
            last = e
    raise SourceUnavailable(f"all NFHL endpoints failed: {last}")


def flood_return_period(lat: float, lon: float) -> list[Measurement]:
    """clm.flood_riverine — return period of the flood the site sits inside.

    Higher is safer: a site in the 100-year floodplain returns 100 and fails the gate;
    a site outside all mapped hazard areas returns 1000.
    """
    fid = "clm.flood_riverine"
    if not _maybe_us(lat, lon):
        return [unknown(
            fid, SOURCE,
            "outside FEMA NFHL coverage (non-US). Use JRC Global Flood Hazard Maps or WRI "
            "Aqueduct floods instead (Tier B, 90 m, coarser). Global flood datasets do not "
            "capture pluvial flash flooding.",
            "years")]

    hit, store = cached(fid, SOURCE, lat, lon, None)
    try:
        if hit is None:
            hit = _query(lat, lon)
            store(hit)

        feats = hit.get("features", [])
        zones = [{
            "zone": (f.get("attributes", {}).get("FLD_ZONE") or "").strip(),
            "subtype": (f.get("attributes", {}).get("ZONE_SUBTY") or "").strip(),
            "sfha": f.get("attributes", {}).get("SFHA_TF"),
        } for f in feats]

        if not zones:
            # No mapped hazard polygon. Inside the US this means outside mapped flood
            # hazard areas; outside the US it means no coverage. Distinguish, because
            # they are opposite conclusions.
            return [measured(
                    fid, 1000, "return_period_years", "A", SOURCE, lat=lat, lon=lon,
                    source_url="https://msc.fema.gov/portal/home",
                    raw={"zones": [], "in_sfha": False},
                notes=("Outside mapped FEMA flood hazard areas. Note that NFHL does not "
                       "model pluvial (flash) flooding, which no widely-available dataset "
                       "captures well — this is a known blind spot, not a clean bill of health."),
            )]

        in_sfha = any(z["sfha"] == "T" or z["zone"] in SFHA_ZONES for z in zones)
        levee = any("LEVEE" in (z["subtype"] or "").upper() for z in zones)
        shaded_x = any("0.2 PCT" in (z["subtype"] or "").upper() for z in zones)

        if in_sfha:
            rp = 100
            note = (f"Inside the FEMA Special Flood Hazard Area (zone "
                    f"{zones[0]['zone']}, 1% annual chance). This is a categorical financing "
                    f"and insurance exclusion, not an engineering judgment — lenders apply it "
                    f"regardless of whether the pad could be elevated.")
        elif levee:
            # Not technically SFHA, but the risk is real and conditional on a structure
            # someone else maintains. Score it as 500-year and say why.
            rp = 500
            note = ("Zone X with REDUCED FLOOD RISK DUE TO LEVEE. Not formally in the SFHA, "
                    "but the protection depends on a levee system maintained by a third "
                    "party, and residual risk on levee failure is severe. Treat as materially "
                    "riskier than an ordinary Zone X: underwriters and lenders frequently "
                    "price it that way, and levee accreditation can lapse.")
        elif shaded_x:
            rp = 500
            note = ("Zone X shaded — 0.2% annual chance (500-year). Buildable, but expect "
                    "elevation requirements and a local flood study for financing.")
        else:
            rp = 1000
            note = (f"Mapped as zone {zones[0]['zone']}, outside the Special Flood Hazard "
                    f"Area. Pluvial flash flooding is not modeled by NFHL.")

        return [measured(
            fid, rp, "return_period_years", "A", SOURCE, lat=lat, lon=lon,
            source_url="https://msc.fema.gov/portal/home",
            raw={"zones": zones[:6], "in_sfha": in_sfha, "levee_protected": levee,
                 "zone_x_shaded": shaded_x},
            notes=note,
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "years")]


def coastal_exposure(lat: float, lon: float, elevation_m: float | None = None) -> list[Measurement]:
    """clm.flood_coastal — not implemented; returns an explicit unknown.

    Coastal freeboard requires a coastal DEM plus a 2050 storm-tide scenario. Inventing
    one would be exactly the fabrication this system forbids, so this records why it
    cannot answer instead of guessing.
    """
    return [unknown(
        "clm.flood_coastal", "noaa_data",
        "coastal SLR adapter not implemented. Requires a coastal DEM (NOAA SLR viewer or "
        "Climate Central CoastalDEM) plus a 2050 storm-tide scenario. Score as N/A for "
        "inland sites more than 50 km from a coastline.",
        "m_freeboard_2050")]

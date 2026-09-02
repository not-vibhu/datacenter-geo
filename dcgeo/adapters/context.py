"""Site context resolution — coordinate to jurisdiction.

Half the factors are jurisdiction-dependent and meaningless without this. Never
analyze a bare coordinate; resolve it first.
"""
from __future__ import annotations

from typing import Any

from .base import SourceUnavailable, cached, http_get

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
SOURCE = "nominatim"

# ISO/RTO and grid operator by country + region. Coarse but enough to route the
# power analyst to the right queue dataset. Refined per-site by the analyst agent.
US_ISO_BY_STATE = {
    "Texas": "ERCOT", "Virginia": "PJM", "Ohio": "PJM", "Pennsylvania": "PJM",
    "Maryland": "PJM", "New Jersey": "PJM", "West Virginia": "PJM", "Delaware": "PJM",
    "Illinois": "PJM/MISO", "Indiana": "MISO/PJM", "Michigan": "MISO", "Wisconsin": "MISO",
    "Minnesota": "MISO", "Iowa": "MISO", "Missouri": "MISO/SPP", "Arkansas": "MISO",
    "Louisiana": "MISO", "Mississippi": "MISO", "Kansas": "SPP", "Oklahoma": "SPP",
    "Nebraska": "SPP", "North Dakota": "MISO/SPP", "South Dakota": "SPP/MISO",
    "California": "CAISO", "New York": "NYISO", "Massachusetts": "ISO-NE",
    "Connecticut": "ISO-NE", "Maine": "ISO-NE", "New Hampshire": "ISO-NE",
    "Vermont": "ISO-NE", "Rhode Island": "ISO-NE",
    "Georgia": "non-ISO (Southern Co.)", "Alabama": "non-ISO (Southern Co.)",
    "Tennessee": "non-ISO (TVA)", "Kentucky": "non-ISO/PJM",
    "North Carolina": "non-ISO (Duke)", "South Carolina": "non-ISO",
    "Florida": "non-ISO (FRCC)", "Arizona": "non-ISO (WECC)", "Nevada": "non-ISO (WECC)",
    "Utah": "non-ISO (WECC)", "Idaho": "non-ISO (WECC)", "Montana": "non-ISO (WECC)",
    "Wyoming": "non-ISO (WECC)", "Colorado": "non-ISO (WECC)", "New Mexico": "non-ISO (WECC)",
    "Oregon": "non-ISO (WECC)", "Washington": "non-ISO (WECC)",
}


def resolve(lat: float, lon: float) -> dict[str, Any]:
    """Reverse-geocode to country / admin1 / admin2 plus market routing hints."""
    hit, store = cached("ctx.admin", SOURCE, lat, lon, None)
    if hit is None:
        try:
            hit = http_get(NOMINATIM, params={
                "lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "addressdetails": 1,
            })
            store(hit)
        except SourceUnavailable as e:
            return {"error": str(e), "country": None, "admin1": None, "admin2": None}

    addr = hit.get("address", {}) or {}
    country = addr.get("country")
    admin1 = addr.get("state") or addr.get("province") or addr.get("region")
    admin2 = addr.get("county") or addr.get("city") or addr.get("district") or addr.get("state_district")
    cc = (addr.get("country_code") or "").upper()

    market = None
    notes = []
    if cc == "US":
        market = US_ISO_BY_STATE.get(admin1 or "", "unknown")
        notes.append("US: interconnection queue data is per-ISO; non-ISO regions have no public "
                     "queue and require utility IRP research (Tier C).")
    elif cc == "IN":
        market = f"DISCOM / {admin1} SERC" if admin1 else "DISCOM"
        notes.append("India: check state DC policy, open-access rules, wheeling and banking "
                     "charges, and CGWB groundwater block status.")
    elif cc == "CN":
        market = f"{admin1} provincial grid" if admin1 else "provincial grid"
        notes.append("China: check 东数西算 (East Data West Computing) hub designation and the "
                     "provincial PUE mandate.")

    return {
        "country": country, "country_code": cc, "admin1": admin1, "admin2": admin2,
        "market": market, "display_name": hit.get("display_name"),
        "guidance": notes, "source": SOURCE,
    }

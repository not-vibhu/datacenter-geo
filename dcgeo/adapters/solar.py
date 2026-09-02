"""NASA POWER — solar irradiance and meteorology. Free, no key, global."""
from __future__ import annotations

from ..models import Measurement
from .base import SourceUnavailable, cached, http_get, measured, unknown

API = "https://power.larc.nasa.gov/api/temporal/climatology/point"
SOURCE = "nasa_power"


def ghi(lat: float, lon: float) -> float | None:
    """Annual mean global horizontal irradiance, kWh/m2/day."""
    hit, store = cached("pwr._ghi", SOURCE, lat, lon, None)
    if hit is None:
        try:
            hit = http_get(API, params={
                "parameters": "ALLSKY_SFC_SW_DWN", "community": "RE",
                "latitude": round(lat, 4), "longitude": round(lon, 4), "format": "JSON",
            }, timeout=60.0)
            store(hit)
        except SourceUnavailable:
            return None
    try:
        vals = hit["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
        ann = vals.get("ANN")
        if ann is None:
            months = [v for k, v in vals.items() if k != "ANN" and v is not None and v > -900]
            ann = sum(months) / len(months) if months else None
        return round(ann, 2) if ann and ann > -900 else None
    except (KeyError, TypeError):
        return None

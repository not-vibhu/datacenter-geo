"""Climate adapter — ERA5 reanalysis via the Open-Meteo archive API.

The single best free source in this system: hourly temperature and humidity anywhere
on Earth, no key, back to 1940. Wet-bulb and free-cooling hours are computed from it
directly, which makes those factors genuinely Tier A worldwide.
"""
from __future__ import annotations

from datetime import date

from ..geo import wet_bulb_stull
from ..models import Measurement
from .base import SourceUnavailable, cached, http_get, measured, unknown

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
SOURCE = "open_meteo_archive"
DEFAULT_YEARS = 10
ARCHIVE_YEARS = 30      # always fetch this much once; shorter windows slice the tail

# Design thresholds. Overridable per analysis via --assume.
WETBULB_THRESHOLD_C = 24.0      # above this, evaporative cooling loses effectiveness
FREE_COOLING_DRYBULB_C = 24.0   # below this, economizer can carry the load at 27 C supply


def _fetch_hourly(lat: float, lon: float, years: int = ARCHIVE_YEARS) -> dict:
    """Hourly 2 m temperature and RH.

    Always fetches and caches ARCHIVE_YEARS regardless of what the caller asked for,
    because the 30-year series subsumes every shorter window and the download is the
    dominant cost in the whole system (~20 MB, tens of seconds). Callers slice the
    tail via `_series(data, years)`.
    """
    years = ARCHIVE_YEARS
    end = date(date.today().year - 1, 12, 31)
    start = date(end.year - years + 1, 1, 1)
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m",
        "timezone": "UTC",
    }
    hit, store = cached("clm._hourly", SOURCE, lat, lon, {"years": ARCHIVE_YEARS})
    if hit:
        return hit
    data = http_get(ARCHIVE, params=params, timeout=120.0)
    if "hourly" not in data:
        raise SourceUnavailable(f"unexpected payload keys: {list(data)[:5]}")
    store(data)
    return data


def _series(data: dict, years: int | None = None) -> tuple[list[float], list[float]]:
    """Paired temperature/RH series, optionally sliced to the most recent `years`."""
    h = data["hourly"]
    temps = [t for t in h.get("temperature_2m", []) if t is not None]
    rhs = [r for r in h.get("relative_humidity_2m", []) if r is not None]
    n = min(len(temps), len(rhs))
    temps, rhs = temps[:n], rhs[:n]
    if years is not None:
        keep = int(years * 8766)
        if keep < n:
            temps, rhs = temps[-keep:], rhs[-keep:]     # most recent years
    return temps, rhs


def wetbulb_hours(lat: float, lon: float, years: int = DEFAULT_YEARS) -> list[Measurement]:
    """wtr.wetbulb_profile — annual hours above the evaporative-cooling threshold.

    Also returns the ASHRAE-convention 0.4% exceedance design wet-bulb, which is the
    number a mechanical engineer will actually size the plant against.
    """
    fid = "wtr.wetbulb_profile"
    try:
        data = _fetch_hourly(lat, lon)
        temps, rhs = _series(data, years)
        if len(temps) < 8760:
            return [unknown(fid, SOURCE, f"only {len(temps)} hourly records returned", "hours")]

        # _series() truncates both to the same length; strict makes that explicit.
        wb = [wet_bulb_stull(t, r) for t, r in zip(temps, rhs, strict=True)]
        n_years = len(wb) / 8766.0
        above = sum(1 for w in wb if w > WETBULB_THRESHOLD_C) / n_years
        design_wb = sorted(wb)[int(len(wb) * 0.996)]      # 0.4% annual exceedance
        mean_wb = sum(wb) / len(wb)

        return [
            measured(
                fid, round(above, 1), f"hours_above_{WETBULB_THRESHOLD_C:.0f}C_wetbulb", "A", SOURCE,
                lat=lat, lon=lon, source_url=ARCHIVE,
                raw={
                    "design_wetbulb_04pct_C": round(design_wb, 2),
                    "mean_wetbulb_C": round(mean_wb, 2),
                    "years": round(n_years, 1),
                    "hours_sampled": len(wb),
                },
                notes=(
                    f"Design wet-bulb (0.4% exceedance) {design_wb:.1f} C; mean {mean_wb:.1f} C. "
                    f"Computed from {n_years:.0f} yr of ERA5 hourly reanalysis via Stull (2011)."
                ),
            )
        ]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "hours")]


def free_cooling_hours(lat: float, lon: float, years: int = DEFAULT_YEARS) -> list[Measurement]:
    """clm.dry_bulb_profile — annual hours where an economizer can carry the load."""
    fid = "clm.dry_bulb_profile"
    try:
        data = _fetch_hourly(lat, lon)
        temps, _ = _series(data, years)
        if len(temps) < 8760:
            return [unknown(fid, SOURCE, f"only {len(temps)} hourly records", "hours")]

        n_years = len(temps) / 8766.0
        free = sum(1 for t in temps if t < FREE_COOLING_DRYBULB_C) / n_years
        design_db = sorted(temps)[int(len(temps) * 0.996)]
        mean_db = sum(temps) / len(temps)
        # Crude but honest PUE proxy: more free-cooling hours -> lower mechanical load.
        pue_proxy = round(1.10 + 0.22 * (1 - free / 8766.0), 3)

        return [
            measured(
                fid, round(free, 1), "free_cooling_hours_per_year", "A", SOURCE,
                lat=lat, lon=lon, source_url=ARCHIVE,
                raw={
                    "design_drybulb_04pct_C": round(design_db, 2),
                    "mean_drybulb_C": round(mean_db, 2),
                    "indicative_annual_pue": pue_proxy,
                    "threshold_C": FREE_COOLING_DRYBULB_C,
                },
                notes=(
                    f"{free:.0f} h/yr below {FREE_COOLING_DRYBULB_C} C. Design dry-bulb "
                    f"{design_db:.1f} C. Indicative PUE {pue_proxy} — a screening proxy, not a "
                    f"CFD-grade model."
                ),
            )
        ]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "hours")]


def heat_projection(lat: float, lon: float, years: int = 30) -> list[Measurement]:
    """clm.extreme_heat_trend — Tier D until a CMIP6 adapter lands.

    Extrapolating an observed trend is NOT a climate projection. It is labeled D and
    the notes say so. Replacing this with NEX-GDDP-CMIP6 is a tracked roadmap item.
    """
    fid = "clm.extreme_heat_trend"
    try:
        data = _fetch_hourly(lat, lon)
        temps, _ = _series(data, years)
        if len(temps) < 8760 * 10:
            return [unknown(fid, SOURCE, "insufficient record for a trend", "delta_C")]

        # Annual 99.6th percentile, then least-squares slope across years.
        per_year: list[float] = []
        for i in range(0, len(temps) - 8760, 8766):
            chunk = sorted(temps[i:i + 8766])
            if len(chunk) > 100:
                per_year.append(chunk[int(len(chunk) * 0.996)])
        n = len(per_year)
        if n < 8:
            return [unknown(fid, SOURCE, f"only {n} complete years", "delta_C")]

        xbar = (n - 1) / 2
        ybar = sum(per_year) / n
        num = sum((i - xbar) * (y - ybar) for i, y in enumerate(per_year))
        den = sum((i - xbar) ** 2 for i in range(n))
        slope = num / den if den else 0.0
        delta_2050 = max(0.0, slope * (2050 - date.today().year))

        return [
            measured(
                fid, round(delta_2050, 2), "delta_C_design_day_2050", "D", SOURCE,
                lat=lat, lon=lon, source_url=ARCHIVE,
                raw={"observed_slope_C_per_year": round(slope, 4), "years_used": n},
                notes=(
                    f"MODELED, NOT PROJECTED: linear extrapolation of the observed {n}-year trend "
                    f"in annual design-day temperature ({slope:+.3f} C/yr). This is a placeholder "
                    f"for NEX-GDDP-CMIP6 and should not be cited as a climate projection."
                ),
            )
        ]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "delta_C")]


def measure_all(lat: float, lon: float, years: int = DEFAULT_YEARS) -> list[Measurement]:
    """One download, three factors."""
    return (wetbulb_hours(lat, lon, years)
            + free_cooling_hours(lat, lon, years)
            + heat_projection(lat, lon, ARCHIVE_YEARS))

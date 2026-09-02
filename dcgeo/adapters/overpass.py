"""OpenStreetMap via Overpass — the infrastructure workhorse.

Serves power (lines, substations, pipelines), land (built-up, industrial), transport
(ports, rail, heavy-haul roads), telecom, and wastewater. One HTTP dialect, many
factors.

Honesty rule: OSM coverage varies enormously by region. Presence of a feature is
evidence; ABSENCE is not evidence of absence. Adapters here downgrade tier to C when
feature density looks implausibly low for a developed area, and say so in the notes.
"""
from __future__ import annotations

import re
from typing import Any

from ..geo import haversine_km
from ..models import Measurement
from .base import SourceUnavailable, cached, http_post, measured, unknown

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
SOURCE = "osm_overpass"
ATTRIB = "https://www.openstreetmap.org/copyright"


def query(ql: str) -> dict[str, Any]:
    """Run Overpass QL against the mirror pool. Raises SourceUnavailable if all fail."""
    last: Exception | None = None
    for url in ENDPOINTS:
        try:
            return http_post(url, data={"data": ql}, timeout=120.0)
        except SourceUnavailable as e:
            last = e
    raise SourceUnavailable(f"all Overpass mirrors failed: {last}")


def _center(el: dict) -> tuple[float, float] | None:
    if "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    if "lat" in el:
        return el["lat"], el["lon"]
    return None


def _voltage_kv(tags: dict) -> float | None:
    """OSM voltage tags are messy: '230000', '400000;110000', '66 kV'. Take the max."""
    raw = tags.get("voltage") or ""
    volts = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", str(raw))]
    if not volts:
        return None
    v = max(volts)
    return v / 1000.0 if v > 1000 else v          # normalize V -> kV


# ── power ────────────────────────────────────────────────────────────────────

def nearest_transmission(
    lat: float, lon: float, radius_km: float = 60.0, min_kv: float = 230.0
) -> list[Measurement]:
    """pwr.transmission_proximity — distance to the nearest line at or above min_kv."""
    fid = "pwr.transmission_proximity"
    params = {"radius_km": radius_km, "min_kv": min_kv}
    hit, store = cached(fid, SOURCE, lat, lon, params)
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:90];
(way["power"="line"](around:{r},{lat},{lon});
 way["power"="cable"](around:{r},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        lines = []
        for el in hit.get("elements", []):
            c = _center(el)
            kv = _voltage_kv(el.get("tags", {}))
            if c and kv is not None:
                lines.append((haversine_km((lat, lon), c), kv, el.get("tags", {})))

        if not lines:
            return [unknown(fid, SOURCE,
                            f"no tagged power lines within {radius_km:.0f} km — OSM coverage "
                            f"may be incomplete here; cross-check Global Energy Monitor", "km")]

        qualifying = sorted((l for l in lines if l[1] >= min_kv), key=lambda x: x[0])
        all_sorted = sorted(lines, key=lambda x: x[0])
        by_kv: dict[float, float] = {}
        for d, kv, _ in all_sorted:
            by_kv[kv] = min(by_kv.get(kv, 1e9), d)

        if not qualifying:
            best_kv = max(l[1] for l in lines)
            return [measured(
                fid, round(all_sorted[0][0], 2), "km", "C", SOURCE, lat=lat, lon=lon,
                source_url=ATTRIB,
                raw={"nearest_any_kv": best_kv, "min_kv_required": min_kv,
                     "distance_by_kv": {str(k): round(v, 2) for k, v in sorted(by_kv.items(), reverse=True)}},
                notes=(f"No line at or above {min_kv:.0f} kV within {radius_km:.0f} km. Nearest line of "
                       f"any voltage is {all_sorted[0][0]:.1f} km at {best_kv:.0f} kV. Tier C: the "
                       f"reported distance does not meet the voltage requirement."),
            )]

        d, kv, tags = qualifying[0]
        n_qual = len(qualifying)
        return [measured(
            fid, round(d, 2), "km", "A", SOURCE, lat=lat, lon=lon, source_url=ATTRIB,
            raw={"voltage_kv": kv, "qualifying_lines": n_qual, "operator": tags.get("operator"),
                 "distance_by_kv": {str(k): round(v, 2) for k, v in sorted(by_kv.items(), reverse=True)}},
            notes=(f"{kv:.0f} kV line at {d:.1f} km; {n_qual} line(s) at or above {min_kv:.0f} kV "
                   f"within {radius_km:.0f} km. Proximity is not capacity — read with "
                   f"pwr.substation_headroom."),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "km")]


def substations(lat: float, lon: float, radius_km: float = 40.0) -> list[Measurement]:
    """pwr.substation_headroom — presence only.

    OSM almost never tags substation CAPACITY. Conflating presence with capacity is
    the most common analytical error in this domain, so this adapter deliberately
    returns an unknown for the headroom factor and puts what it found in the notes
    for the power analyst to research further.
    """
    fid = "pwr.substation_headroom"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:90];
(node["power"="substation"](around:{r},{lat},{lon});
 way["power"="substation"](around:{r},{lat},{lon});
 relation["power"="substation"](around:{r},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        found = []
        for el in hit.get("elements", []):
            c = _center(el)
            if not c:
                continue
            t = el.get("tags", {})
            found.append({
                "distance_km": round(haversine_km((lat, lon), c), 2),
                "voltage_kv": _voltage_kv(t),
                "name": t.get("name"),
                "operator": t.get("operator"),
                "substation_type": t.get("substation"),
            })
        found.sort(key=lambda x: x["distance_km"])
        transmission = [f for f in found if (f["voltage_kv"] or 0) >= 110]

        if not found:
            return [unknown(fid, SOURCE,
                            f"no substations tagged within {radius_km:.0f} km", "MVA")]

        nearest = transmission[0] if transmission else found[0]
        return [unknown(
            fid, SOURCE,
            f"OSM does not publish substation capacity. Found {len(found)} substation(s) within "
            f"{radius_km:.0f} km ({len(transmission)} at >=110 kV); nearest qualifying is "
            f"{nearest['name'] or 'unnamed'} at {nearest['distance_km']} km, "
            f"{nearest['voltage_kv'] or '?'} kV. Headroom must be obtained from the utility's "
            f"IRP or transmission planning study.",
            "MVA",
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "MVA")]


def gas_pipeline_distance(lat: float, lon: float, radius_km: float = 50.0) -> float | None:
    """Component of pwr.onsite_generation_potential. Returns km or None."""
    r = int(radius_km * 1000)
    ql = f"""[out:json][timeout:90];
(way["man_made"="pipeline"]["substance"~"^(gas|natural_gas)$"](around:{r},{lat},{lon});
 way["man_made"="pipeline"]["type"="gas"](around:{r},{lat},{lon}););
out tags center;"""
    hit, store = cached("pwr._gas_pipeline", SOURCE, lat, lon, {"radius_km": radius_km})
    if hit is None:
        hit = query(ql)
        store(hit)
    ds = [haversine_km((lat, lon), c) for el in hit.get("elements", []) if (c := _center(el))]
    return round(min(ds), 2) if ds else None


# ── land ─────────────────────────────────────────────────────────────────────

def developable_area(lat: float, lon: float, radius_km: float = 5.0) -> list[Measurement]:
    """lnd.contiguous_area — screening estimate from OSM exclusions.

    Deliberately conservative and explicitly an upper bound on ACQUIRABLE land. The
    proper implementation masks ESA WorldCover against slope and protected areas;
    this OSM-based version is the keyless fallback and is tiered accordingly.
    """
    fid = "lnd.contiguous_area"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:120];
(way["landuse"~"^(residential|commercial|retail|military|cemetery|quarry)$"](around:{r},{lat},{lon});
 way["natural"~"^(water|wetland|wood)$"](around:{r},{lat},{lon});
 way["building"](around:{r},{lat},{lon});
 way["landuse"~"^(industrial|farmland|meadow|grass|brownfield|greenfield)$"](around:{r},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        import math
        circle_ha = math.pi * (radius_km ** 2) * 100
        els = hit.get("elements", [])
        excl = {"residential", "commercial", "retail", "military", "cemetery", "quarry"}
        favorable = {"industrial", "farmland", "meadow", "grass", "brownfield", "greenfield"}

        n_excluded = sum(1 for e in els if e.get("tags", {}).get("landuse") in excl
                         or e.get("tags", {}).get("natural") in {"water", "wetland", "wood"})
        n_buildings = sum(1 for e in els if "building" in e.get("tags", {}))
        n_favorable = sum(1 for e in els if e.get("tags", {}).get("landuse") in favorable)

        # Screening heuristic: building density is the dominant signal for whether
        # a large contiguous pad can exist at all.
        density = n_buildings / max(circle_ha / 100, 1)      # buildings per km^2
        if density > 400:
            frac = 0.02
            character = "dense urban"
        elif density > 120:
            frac = 0.08
            character = "suburban"
        elif density > 30:
            frac = 0.25
            character = "exurban / village"
        elif density > 5:
            frac = 0.45
            character = "rural with settlement"
        else:
            frac = 0.65
            character = "open rural"
        if n_favorable > 0:
            frac = min(0.85, frac + 0.08)

        est_ha = round(circle_ha * frac, 1)
        return [measured(
            fid, est_ha, "hectares", "C", SOURCE, lat=lat, lon=lon, source_url=ATTRIB,
            raw={"radius_km": radius_km, "buildings": n_buildings,
                 "buildings_per_km2": round(density, 1), "excluded_polygons": n_excluded,
                 "favorable_landuse_polygons": n_favorable, "character": character,
                 "assumed_developable_fraction": frac},
            notes=(f"SCREENING ESTIMATE ONLY. {character} ({density:.0f} buildings/km2) within "
                   f"{radius_km} km; assumed {frac:.0%} developable. This is an upper bound on "
                   f"physically developable land and a much looser upper bound on ACQUIRABLE land — "
                   f"parcel fragmentation typically cuts it by half or more. Confirm against "
                   f"cadastral data before any decision."),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "hectares")]


def dwellings_within(lat: float, lon: float, radius_km: float = 1.0) -> list[Measurement]:
    """com.residential_proximity — residential building count in the noise buffer."""
    fid = "com.residential_proximity"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:90];
(way["building"~"^(residential|house|apartments|detached|semidetached_house|terrace|dormitory)$"](around:{r},{lat},{lon});
 node["building"~"^(residential|house|apartments|detached)$"](around:{r},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        els = hit.get("elements", [])
        count = 0
        for e in els:
            bt = e.get("tags", {}).get("building")
            # An apartment block is many dwellings; count levels when tagged.
            if bt in ("apartments", "dormitory"):
                levels = e.get("tags", {}).get("building:levels")
                try:
                    count += max(4, int(float(levels)) * 4) if levels else 12
                except (TypeError, ValueError):
                    count += 12
            else:
                count += 1

        tier = "A" if count > 0 else "C"
        return [measured(
            fid, count, f"dwellings_within_{radius_km:.0f}km", tier, SOURCE, lat=lat, lon=lon,
            source_url=ATTRIB,
            raw={"raw_features": len(els), "radius_km": radius_km},
            notes=(f"{count} estimated dwellings from {len(els)} OSM residential features within "
                   f"{radius_km} km. Apartment blocks estimated at 4 units/level. Noise from "
                   f"chillers and generator testing is the most common specific complaint in data "
                   f"center opposition — distance is the cheapest mitigation."
                   + ("" if count else " Zero count may reflect sparse OSM building coverage rather "
                                       "than genuinely empty land; tier lowered to C.")),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "dwellings")]


def brownfield_signals(lat: float, lon: float, radius_km: float = 8.0) -> list[Measurement]:
    """lnd.brownfield_opportunity — industrial reuse and retired-asset detection."""
    fid = "lnd.brownfield_opportunity"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:90];
(way["landuse"="brownfield"](around:{r},{lat},{lon});
 way["landuse"="industrial"](around:{r},{lat},{lon});
 way["power"="plant"](around:{r},{lat},{lon});
 node["power"="plant"](around:{r},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        plants, brown, indus = [], 0, 0
        for e in hit.get("elements", []):
            t = e.get("tags", {})
            if t.get("power") == "plant":
                c = _center(e)
                plants.append({
                    "distance_km": round(haversine_km((lat, lon), c), 2) if c else None,
                    "source": t.get("plant:source"), "name": t.get("name"),
                    "output_mw": t.get("plant:output:electricity"),
                })
            elif t.get("landuse") == "brownfield":
                brown += 1
            elif t.get("landuse") == "industrial":
                indus += 1

        plants.sort(key=lambda p: p["distance_km"] or 1e9)
        if plants:
            cat, note = "heavy_industrial_reuse", (
                f"{len(plants)} power plant(s) within {radius_km:.0f} km; nearest "
                f"{plants[0].get('name') or 'unnamed'} ({plants[0].get('source') or 'unknown fuel'}) "
                f"at {plants[0]['distance_km']} km. CHECK RETIREMENT STATUS — a retiring plant is "
                f"the highest-value site category available, because interconnection rights, "
                f"transmission, water rights and often the land itself are already in place.")
        elif brown:
            cat, note = "light_industrial_reuse", f"{brown} brownfield parcel(s) mapped nearby."
        elif indus:
            cat, note = "light_industrial_reuse", f"{indus} industrial land parcel(s) nearby."
        else:
            cat, note = "greenfield_clean", "No industrial or generation reuse signal in OSM."

        return [measured(
            fid, cat, "category", "C", SOURCE, lat=lat, lon=lon, source_url=ATTRIB,
            raw={"power_plants": plants[:5], "brownfield_polygons": brown, "industrial_polygons": indus},
            notes=note,
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "category")]


# ── transport & telecom ──────────────────────────────────────────────────────

def port_rail_access(lat: float, lon: float, radius_km: float = 150.0) -> list[Measurement]:
    """eco.port_rail_access — distance to heavy-lift-capable port or rail."""
    fid = "eco.port_rail_access"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:120];
(way["industrial"="port"](around:{r},{lat},{lon});
 node["harbour"="yes"](around:{r},{lat},{lon});
 way["landuse"="port"](around:{r},{lat},{lon});
 node["railway"="station"]["train"="yes"](around:{r},{lat},{lon});
 way["railway"="rail"]["usage"="main"](around:{min(r, 40000)},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        ports, rails = [], []
        for e in hit.get("elements", []):
            c = _center(e)
            if not c:
                continue
            d = haversine_km((lat, lon), c)
            t = e.get("tags", {})
            if t.get("industrial") == "port" or t.get("harbour") == "yes" or t.get("landuse") == "port":
                ports.append(d)
            else:
                rails.append(d)

        candidates = ports + rails
        best = min(candidates) if candidates else None
        if best is None:
            return [unknown(fid, SOURCE, f"no port or main-line rail within {radius_km:.0f} km", "km")]

        return [measured(
            fid, round(best, 2), "km_to_capable_port_or_rail", "B", SOURCE, lat=lat, lon=lon,
            source_url=ATTRIB,
            raw={"nearest_port_km": round(min(ports), 2) if ports else None,
                 "nearest_rail_km": round(min(rails), 2) if rails else None},
            notes=("Read together with lnd.heavy_haul_access: a nearby port is worthless if the "
                   "final approach cannot carry a 300-tonne transformer. OSM port tagging is "
                   "inconsistent; treat as screening-grade."),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "km")]


def wwtp_distance(lat: float, lon: float, radius_km: float = 40.0) -> list[Measurement]:
    """wtr.reclaimed_availability — nearest wastewater treatment plant."""
    fid = "wtr.reclaimed_availability"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:90];
(way["man_made"="wastewater_plant"](around:{r},{lat},{lon});
 node["man_made"="wastewater_plant"](around:{r},{lat},{lon});
 way["man_made"="water_works"](around:{r},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        found = []
        for e in hit.get("elements", []):
            c = _center(e)
            if c:
                found.append((haversine_km((lat, lon), c), e.get("tags", {}).get("name")))
        if not found:
            return [unknown(fid, SOURCE,
                            f"no wastewater treatment plant mapped within {radius_km:.0f} km", "km")]
        found.sort()
        d, name = found[0]
        return [measured(
            fid, round(d, 2), "km_to_wwtp", "B", SOURCE, lat=lat, lon=lon, source_url=ATTRIB,
            raw={"name": name, "plants_found": len(found)},
            notes=("Distance only — treated flow capacity must be confirmed with the operator. "
                   "Reclaimed water is usually the highest score-per-dollar water intervention "
                   "available: it neutralizes most community opposition and is often cheaper than "
                   "potable."),
        )]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "km")]


def fiber_proximity(lat: float, lon: float, radius_km: float = 30.0) -> list[Measurement]:
    """cnx.longhaul_fiber_proximity — OSM telecom, with an honest tier.

    Terrestrial fiber is the weakest data availability in this whole framework:
    carriers treat routes as confidential. Where OSM has nothing, this returns an
    unknown rather than inventing a proxy.
    """
    fid = "cnx.longhaul_fiber_proximity"
    hit, store = cached(fid, SOURCE, lat, lon, {"radius_km": radius_km})
    try:
        if hit is None:
            r = int(radius_km * 1000)
            ql = f"""[out:json][timeout:90];
(way["telecom"="line"](around:{r},{lat},{lon});
 way["communication"="line"](around:{r},{lat},{lon});
 way["man_made"="cable"](around:{r},{lat},{lon});
 node["telecom"="exchange"](around:{r},{lat},{lon});
 way["telecom"="data_center"](around:{r},{lat},{lon});
 node["telecom"="data_center"](around:{r},{lat},{lon}););
out tags center;"""
            hit = query(ql)
            store(hit)

        routes, facilities = [], []
        for e in hit.get("elements", []):
            c = _center(e)
            if not c:
                continue
            d = haversine_km((lat, lon), c)
            t = e.get("tags", {})
            (facilities if t.get("telecom") in ("exchange", "data_center") else routes).append((d, t.get("name")))

        if routes:
            routes.sort()
            return [measured(
                fid, round(routes[0][0], 2), "km", "C", SOURCE, lat=lat, lon=lon, source_url=ATTRIB,
                raw={"routes_found": len(routes), "facilities_found": len(facilities)},
                notes=("OSM telecom route coverage is sparse and inconsistent worldwide. Tier C "
                       "even when a route is found. Confirm with carriers or a paid route dataset."),
            )]
        if facilities:
            facilities.sort()
            return [measured(
                fid, round(facilities[0][0], 2), "km", "D", SOURCE, lat=lat, lon=lon, source_url=ATTRIB,
                raw={"facilities_found": len(facilities), "inferred_from": "telecom facility proximity"},
                notes=("INFERRED, NOT MEASURED: no fiber routes mapped; distance is to the nearest "
                       "telecom exchange or data center, used as a proxy for route presence. Tier D."),
            )]
        return [unknown(fid, SOURCE,
                        f"no telecom routes or facilities mapped within {radius_km:.0f} km. "
                        f"Absence in OSM is NOT evidence of absence — carriers do not publish "
                        f"routes. Requires carrier enquiry or a paid route dataset.", "km")]
    except SourceUnavailable as e:
        return [unknown(fid, SOURCE, str(e), "km")]

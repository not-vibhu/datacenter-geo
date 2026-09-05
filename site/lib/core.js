/** Pure atlas rules, shared by the UI and dependency-free regression tests. */
export const REGIONS = {
  bhopal: {
    name: "Bhopal",
    subtitle: "Madhya Pradesh, India",
    center: [23.2599, 77.4126],
    zoom: 12,
    bbox: [23.08, 77.18, 23.48, 77.65],
  },
  mp: {
    name: "Madhya Pradesh",
    subtitle: "Central India · regional exploration",
    center: [23.5, 78.3],
    zoom: 7,
    bbox: [21.05, 74.02, 26.9, 82.85],
  },
  india: {
    name: "India",
    subtitle: "National infrastructure landscape",
    center: [22.5, 79.1],
    zoom: 5,
    bbox: [6.5, 68, 37, 97.5],
  },
};
export const DEFAULT_LAYERS = {
  facilities: true,
  substation: true,
  line: true,
  water: true,
  industrial: false,
  extent: false,
};
export const STATUS = {
  listed: "Directory listed",
  documented: "Government documented",
  upcoming: "Upcoming",
  candidate: "Candidate boundary",
  existing: "Facility boundary",
};
export const LAYERS = {
  facilities: {
    name: "Data centers & facilities",
    note: "India · directory and documented sites",
    color: "#20614f",
  },
  substation: {
    name: "Substations",
    note: "Bhopal pilot · capacity unverified",
    color: "#d69540",
  },
  line: {
    name: "Power lines",
    note: "Bhopal pilot · mapped routes",
    color: "#dfaa4c",
  },
  water: {
    name: "Water bodies",
    note: "Bhopal pilot · not a flood layer",
    color: "#70afd0",
  },
  industrial: {
    name: "Industrial land use",
    note: "Bhopal pilot · not available parcels",
    color: "#ae8eae",
  },
  extent: {
    name: "Study coverage",
    note: "Bhopal pilot extent, not city limits",
    color: "#809c77",
  },
};
export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export function safeURL(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
export function located(f) {
  return (
    typeof f.lat === "number" &&
    typeof f.lon === "number" &&
    Number.isFinite(f.lat) &&
    Number.isFinite(f.lon) &&
    Math.abs(f.lat) <= 90 &&
    Math.abs(f.lon) <= 180
  );
}
export function inRegion(f, region) {
  if (region === "india") return true;
  if (region === "bhopal")
    return (
      /bhopal/i.test(f.city || "") ||
      (located(f) && within(f.lat, f.lon, REGIONS.bhopal.bbox))
    );
  return (
    /^(mp|madhya pradesh)$/i.test((f.state || "").trim()) ||
    /^(bhopal|indore|gwalior|jabalpur)$/i.test((f.city || "").trim())
  );
}
export function within(lat, lon, [south, west, north, east]) {
  return lat >= south && lat <= north && lon >= west && lon <= east;
}
export function filterFacilities(
  facilities,
  { region = "bhopal", query = "", status = "all" } = {},
) {
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return facilities
    .filter(
      (f) =>
        inRegion(f, region) &&
        (status === "all" || f.status === status) &&
        terms.every((term) =>
          `${f.name} ${f.city} ${f.state} ${f.source}`
            .toLowerCase()
            .includes(term),
        ),
    )
    .sort(
      (a, b) =>
        Number(a.status === "upcoming") - Number(b.status === "upcoming") ||
        a.name.localeCompare(b.name),
    );
}
export function parseCoordinates(text) {
  if (!/^\s*[+-]?\d+(?:\.\d+)?\s*[, ]\s*[+-]?\d+(?:\.\d+)?\s*$/.test(text))
    return null;
  const parts = text
    .trim()
    .split(/[,\s]+/)
    .map(Number);
  return parts.length === 2 &&
    Math.abs(parts[0]) <= 90 &&
    Math.abs(parts[1]) <= 180
    ? parts
    : null;
}
export function bandsOverlap(a, b) {
  return (
    a.score != null &&
    b.score != null &&
    Math.abs(a.score - b.score) <= a.band + b.band
  );
}

/** Isolate missing sections: a broken overlay must not hide the facility directory. */
export function normalizeAtlas(raw) {
  const issues = [];
  const data = {
    facilities: [],
    overlays: { features: [], study_bbox: REGIONS.bhopal.bbox },
    proximity: { cells: [] },
    meta: { ...(raw?.meta || {}) },
  };
  if (Array.isArray(raw?.facilities))
    data.facilities = raw.facilities.filter(
      (f) => f && typeof f.id === "string" && typeof f.name === "string",
    );
  else {
    issues.push("Facility directory unavailable");
    delete data.meta.retrieved;
  }
  if (Array.isArray(raw?.overlays?.features))
    data.overlays = { ...raw.overlays, study_bbox: REGIONS.bhopal.bbox };
  else {
    issues.push("Infrastructure overlays unavailable");
    delete data.meta.osm_retrieved;
    data.meta.overlay_counts = {};
  }
  if (Array.isArray(raw?.proximity?.cells)) data.proximity = raw.proximity;
  else issues.push("Power proximity surface unavailable");
  return { data, issues };
}
export function readView(hash, facilities = []) {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const region = Object.hasOwn(REGIONS, p.get("region"))
    ? p.get("region")
    : "bhopal";
  const view = (p.get("view") || "").split(",").map(Number);
  const validView =
    view.length === 3 &&
    view.every(Number.isFinite) &&
    Math.abs(view[0]) <= 85 &&
    Math.abs(view[1]) <= 180 &&
    view[2] >= 3 &&
    view[2] <= 20;
  const layers = p.has("layers")
    ? Object.fromEntries(
        Object.keys(DEFAULT_LAYERS).map((k) => [
          k,
          p.get("layers").split(",").includes(k),
        ]),
      )
    : { ...DEFAULT_LAYERS };
  const opacity = Number(p.get("opacity"));
  return {
    layers,
    opacity:
      p.has("opacity") &&
      Number.isFinite(opacity) &&
      opacity >= 0.15 &&
      opacity <= 0.9
        ? opacity
        : 0.55,
    region,
    center: validView ? view.slice(0, 2) : REGIONS[region].center,
    zoom: validView ? view[2] : REGIONS[region].zoom,
    basemap: ["light", "satellite", "terrain"].includes(p.get("base"))
      ? p.get("base")
      : "light",
    heat: ["density", "power", "none"].includes(p.get("heat"))
      ? p.get("heat")
      : region === "india"
        ? "density"
        : "none",
    selected: facilities.some((f) => f.id === p.get("facility"))
      ? p.get("facility")
      : null,
  };
}
export function viewHash(state, center, zoom) {
  const p = new URLSearchParams({
    region: state.region,
    view: `${center.lat.toFixed(5)},${center.lng.toFixed(5)},${zoom}`,
    base: state.basemap,
    heat: state.heat,
  });
  if (state.layers)
    p.set(
      "layers",
      Object.keys(state.layers)
        .filter((k) => state.layers[k])
        .join(","),
    );
  if (state.opacity != null) p.set("opacity", String(state.opacity));
  if (state.selected?.type === "facility") p.set("facility", state.selected.id);
  return `#${p}`;
}

/** Strict GeoJSON contract: preserve every ring/vertex, never substitute a radius. */
export function boundaryFeatures(raw, turf) {
  const features =
    raw?.type === "FeatureCollection"
      ? raw.features
      : raw?.type === "Feature"
        ? [raw]
        : [{ type: "Feature", geometry: raw, properties: {} }];
  if (!Array.isArray(features) || !features.length || features.length > 100)
    throw new Error("Import between 1 and 100 polygon features.");
  return features.map((feature, index) => {
    const geom = feature?.geometry;
    if (!geom || !["Polygon", "MultiPolygon"].includes(geom.type))
      throw new Error(
        `Feature ${index + 1}: a Polygon or MultiPolygon is required.`,
      );
    const polygons =
      geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
    let count = 0;
    if (!Array.isArray(polygons) || !polygons.length)
      throw new Error("Empty polygon geometry.");
    for (const polygon of polygons) {
      if (!Array.isArray(polygon) || !polygon.length)
        throw new Error("A polygon needs an exterior ring.");
      for (const ring of polygon) {
        if (!Array.isArray(ring) || ring.length < 4)
          throw new Error(
            "Each ring needs at least 3 vertices and a closing point.",
          );
        count += ring.length;
        for (const coord of ring) {
          if (
            !Array.isArray(coord) ||
            coord.length !== 2 ||
            !coord.every(Number.isFinite) ||
            Math.abs(coord[0]) > 180 ||
            Math.abs(coord[1]) > 90
          )
            throw new Error(
              "Use finite WGS84 [longitude, latitude] coordinates.",
            );
        }
        if (ring[0][0] !== ring.at(-1)[0] || ring[0][1] !== ring.at(-1)[1])
          throw new Error("Every polygon ring must be closed.");
      }
    }
    if (count > 10000)
      throw new Error("Limit each boundary to 10,000 vertices.");
    const clean = {
      type: "Feature",
      geometry: structuredClone(geom),
      properties: {},
    };
    if (
      !turf.booleanValid(clean) ||
      turf.kinks(clean).features.length ||
      turf.area(clean) < 1
    )
      throw new Error(
        "Boundary must have positive area with no crossing edges or invalid holes.",
      );
    return {
      ...clean,
      properties: {
        name: String(
          feature.properties?.name || `Imported boundary ${index + 1}`,
        ).slice(0, 120),
        kind:
          feature.properties?.kind === "existing" ? "existing" : "candidate",
        notes: String(feature.properties?.notes || "").slice(0, 2000),
        facility_id:
          typeof feature.properties?.facility_id === "string"
            ? feature.properties.facility_id.slice(0, 120)
            : null,
      },
    };
  });
}
export function loadSaved(storage, turf) {
  const value = storage.getItem("dcgeo.boundaries.v1");
  if (!value) return [];
  const stored = JSON.parse(value);
  if (stored.version !== 1 || !Array.isArray(stored.features))
    throw new Error("Unsupported boundary storage version.");
  if (!stored.features.length) return [];
  const validated = boundaryFeatures(
    { type: "FeatureCollection", features: stored.features },
    turf,
  );
  return validated.map((f, i) => ({
    ...f,
    id: stored.features[i].id || `restored-${i}`,
    properties: {
      ...f.properties,
      created: stored.features[i].properties?.created,
      updated: stored.features[i].properties?.updated,
      boundary_status: "user_drawn_unverified",
    },
  }));
}

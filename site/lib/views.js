import {
  esc,
  safeURL,
  REGIONS,
  STATUS,
  LAYERS,
  located,
  filterFacilities,
} from "./core.js";
import { icon } from "./icons.js";

export const fmt = (n) =>
  Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const button = (action, label, glyph = "arrow", primary = false) =>
  `<button class="button ${primary ? "primary" : ""}" data-action="${action}">${icon(glyph)}${label}</button>`;
const sourceLink = (url, name) =>
  safeURL(url)
    ? `<a class="text-link" href="${esc(safeURL(url))}" target="_blank" rel="noopener">${esc(name)} ${icon("arrow")}</a>`
    : `<span class="text-link">Source URL unavailable</span>`;
const head = (overline, title, subtitle, glyph = "crosshair", tags = "") =>
  `<div class="detail-top"><div class="detail-overline"><span class="eyebrow">${esc(overline)}</span><button class="detail-close" data-action="overview" aria-label="Close details">${icon("close")}</button></div><div class="detail-symbol">${icon(glyph)}</div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p>${tags ? `<div class="detail-tags">${tags}</div>` : ""}</div>`;
const tag = (text, amber = false) =>
  `<span class="tag ${amber ? "amber" : ""}">${esc(text)}</span>`;

export function exploreView(state, data, facilities) {
  return `<div class="section-label">EXPLORE AT ANY SCALE</div><div class="region-grid">${Object.entries(
    REGIONS,
  )
    .reverse()
    .map(
      ([key, r]) =>
        `<button class="region-card ${state.region === key ? "active" : ""}" data-region="${key}"><strong>${key === "mp" ? "MP" : r.name}</strong><small>${key === "india" ? "COUNTRY" : key === "mp" ? "STATE" : "PILOT CITY"}</small></button>`,
    )
    .join("")}</div>
    <div class="section-label">${state.query ? "SEARCHING ALL INDIA" : "FACILITY INVENTORY"}<span class="count">${facilities.length}</span></div>
    <div class="filter-row"><select id="status-filter" aria-label="Facility status">${[["all", "All statuses"], ...Object.entries(STATUS).slice(0, 3)].map(([k, v]) => `<option value="${k}" ${state.status === k ? "selected" : ""}>${v}</option>`).join("")}</select><button class="button" data-action="fit-results" title="Fit matching facilities in map">${icon("frame")}</button></div>
    ${
      facilities
        .slice(0, state.limit)
        .map(
          (f) =>
            `<button class="facility-card ${state.selected?.id === f.id ? "selected" : ""}" data-facility="${esc(f.id)}"><span class="facility-mark ${f.status}">${icon(f.status === "upcoming" ? "clock" : "server")}</span><span class="facility-copy"><strong>${esc(f.name)}</strong><span class="location">${esc(f.city || f.state || "India")}${!located(f) ? " · location unverified" : ""}</span><span class="card-foot"><span><i class="status-dot ${f.status}"></i>${esc(STATUS[f.status])}</span><span class="tier-badge">TIER ${esc(f.tier)}</span></span></span></button>`,
        )
        .join("") ||
      `<div class="empty">${icon("search")}<strong>No matching facilities</strong>Search a listed city, facility name, or enter latitude, longitude.<button class="text-link" data-action="clear-search">Clear search & filters</button></div>`
    }
    ${facilities.length > state.limit ? `<button class="button full" data-action="more">Show more (${facilities.length - state.limit} remaining)</button>` : ""}
    <div class="notice">${data.meta?.coverage || "Facility inventory is temporarily unavailable."}<br><button class="text-link" data-action="sources">Sources & coverage ${icon("arrow")}</button></div>`;
}
export function layersView(state, data) {
  return `<div class="section-label">INFRASTRUCTURE OVERLAYS</div><div class="layer-group">${Object.entries(
    LAYERS,
  )
    .map(
      ([id, item]) =>
        `<label class="layer-row"><input type="checkbox" data-layer="${id}" ${state.layers[id] ? "checked" : ""}><span class="layer-line" style="background:${item.color}"></span><span><strong>${item.name}</strong><small>${item.note}</small></span><span class="layer-total">${id === "facilities" ? data.facilities.filter(located).length : (data.meta?.overlay_counts?.[id] ?? "")}</span></label>`,
    )
    .join("")}</div>
    <div class="section-label">HEATMAPS <span class="count">EXPLORATORY</span></div><div class="heat-options">${[
      ["none", "No heatmap"],
      ["density", "Facility density · India"],
      ["power", "Power proximity · Bhopal"],
    ]
      .map(
        ([id, text]) =>
          `<label><input type="radio" name="heatmap" data-heat="${id}" ${state.heat === id ? "checked" : ""}>${text}</label>`,
      )
      .join(
        "",
      )}<small>${state.heat === "density" ? "Relative concentration of located directory records. Each facility has equal weight; no capacity is inferred." : state.heat === "power" ? "Distance to mapped substations on a 2 km sample grid. A research signal, not available power or a suitability score." : "Enable a heatmap to explore a specific signal."}</small><div class="opacity-label"><span>OPACITY</span><span id="opacity-value">${Math.round(state.opacity * 100)}%</span></div><input id="heat-opacity" type="range" min="15" max="90" value="${state.opacity * 100}" aria-label="Heatmap opacity"></div>
    <div class="notice amber"><strong>Investment suitability is not yet mapped.</strong><br>Power capacity, land availability, flood risk and permissions still need evidence. Unmapped areas have unknown potential.</div><button class="text-link" data-action="sources">Inspect source coverage ${icon("arrow")}</button>`;
}
export function savedView(saved) {
  return `<div class="section-label">YOUR SITE BOUNDARIES <span class="count">${saved.length}</span></div>${saved.map((f) => `<button class="facility-card" data-boundary="${esc(f.id)}"><span class="facility-mark">${icon("polygon")}</span><span class="facility-copy"><strong>${esc(f.properties.name)}</strong><span class="location">${esc(STATUS[f.properties.kind])}</span><span class="card-foot">${fmt(turf.area(f) / 10000)} ha<span class="tier-badge">DRAFT</span></span></span></button>`).join("") || `<div class="empty">${icon("polygon")}<strong>A place to build your shortlist</strong>Draw a boundary on the map, name it and save it here.</div>`}<div class="actions">${button("draw", "Draw boundary", "polygon", true)}${button("import", "Import", "upload")}</div>${saved.length ? `<button class="button full" data-action="export-all">${icon("download")}Export all boundaries</button>` : ""}<div class="notice">Saved on this browser only. Export GeoJSON to back up your work or move it to another device. Draft boundaries are not surveyed ownership records.</div>`;
}
export function overviewView(state, data, saved) {
  const region = REGIONS[state.region],
    facilities = filterFacilities(data.facilities, { region: state.region });
  const mapped = data.meta?.retrieved ? facilities.filter(located).length : "—";
  const local = state.region === "bhopal";
  return (
    head(
      "REGION BRIEF",
      region.name,
      local
        ? "Your starting point for AI infrastructure research."
        : "Follow the infrastructure. Investigate the evidence.",
      "map",
      tag(local ? "ACTIVE PILOT" : "EXPLORATION") +
        tag("Evidence before investment"),
    ) +
    `<div class="detail-body"><div class="metric-grid"><div class="metric"><strong>${mapped}</strong><span>located facility records</span></div><div class="metric"><strong>${saved.length}</strong><span>saved boundaries · all regions</span></div></div>
    <div class="detail-section"><h3>WHAT YOU CAN EXPLORE</h3><div class="coverage-row">Facility directory<span class="${data.meta?.retrieved ? "available" : ""}">${data.meta?.retrieved ? "India coverage" : "Unavailable"}</span></div><div class="coverage-row">Power & land context<span class="${data.meta?.osm_retrieved ? "available" : ""}">${data.meta?.osm_retrieved ? "Bhopal pilot" : "Unavailable"}</span></div><div class="coverage-row">Exact site boundaries<span class="available">Draw or import</span></div><div class="coverage-row">Spare power & land title<span>Not verified</span></div><div class="coverage-row">Investment suitability<span>Not yet mapped</span></div></div>
    <div class="detail-section"><h3>START WITH A SITE</h3><div class="step-card"><span class="step-number">1</span><div><strong>Get close to the ground</strong><p>Zoom into a facility or search coordinates. Switch to satellite to inspect the site.</p></div></div><div class="step-card"><span class="step-number">2</span><div><strong>Trace the boundary</strong><p>Place vertices around the site. Edit the outline and save the exact geometry.</p></div></div><div class="step-card"><span class="step-number">3</span><div><strong>Build the evidence</strong><p>Export the parcel into the analysis workflow. Verify capacity, rights and hazards next.</p></div></div></div><button class="button primary full" data-action="draw">${icon("polygon")}Draw a site boundary</button><div class="notice">${local ? "Bhopal is the infrastructure pilot. Expand to MP for the regional facility directory, then India for the national density heatmap." : "Heatmap colors describe the selected data source. A concentration of facilities or substations is a research lead, not proof of investment suitability."}</div></div>`
  );
}
export function facilityView(f) {
  return (
    head(
      "FACILITY RECORD",
      f.name,
      [f.city, f.state, "India"].filter(Boolean).join(" · "),
      "server",
      tag(STATUS[f.status], f.status === "upcoming") +
        tag(`Evidence tier ${f.tier}`),
    ) +
    `<div class="detail-body"><dl class="facts"><div><dt>Coordinates</dt><dd>${located(f) ? `<code>${f.lat.toFixed(6)}, ${f.lon.toFixed(6)}</code>` : "Awaiting verified coordinates"}</dd></div><div><dt>Location precision</dt><dd>${esc(f.coordinate_precision)}</dd></div><div><dt>IT load / spare capacity</dt><dd>Not verified</dd></div><div><dt>Facility boundary</dt><dd>Not verified · draw a research draft</dd></div><div><dt>Source</dt><dd>${esc(f.source)} · ${esc(f.retrieved?.slice(0, 10))}${sourceLink(f.source_url, "Open source record")}</dd></div></dl><div class="notice">${esc(f.notes)}</div>${located(f) ? `<div class="actions">${button("satellite-site", "Inspect imagery", "satellite")}${button("draw-facility", "Trace boundary", "polygon", true)}</div>` : `<div class="notice amber">This project is listed for Bhopal but has no verified point. It is excluded from map pins and the density heatmap.</div>`}<div class="detail-section"><h3>VERIFY NEXT</h3><p>Confirm operator status, exact parcel outline, sanctioned load and available capacity. A directory listing alone does not establish any of these.</p></div></div>`
  );
}
export function overlayView(feature) {
  const p = feature.properties;
  return (
    head(
      "MAPPED INFRASTRUCTURE",
      p.name || LAYERS[p.category]?.name || "Mapped feature",
      "OpenStreetMap · Bhopal pilot",
      p.category === "substation" || p.category === "line" ? "bolt" : "map",
      tag("Mapped geometry") + tag(`Evidence tier ${p.tier}`),
    ) +
    `<div class="detail-body"><dl class="facts"><div><dt>Feature</dt><dd>${esc(feature.id)}</dd></div><div><dt>Voltage tag</dt><dd>${esc(p.voltage ? `${p.voltage} V (source tag)` : "Not recorded")}</dd></div><div><dt>Operator tag</dt><dd>${esc(p.operator || "Not recorded")}</dd></div><div><dt>Retrieved</dt><dd>${esc(p.retrieved.slice(0, 10))}</dd></div></dl><div class="notice">Mapped infrastructure does not establish spare capacity, rights to connect, flood safety or available land. Source geometry has not been surveyed by this project.</div>${sourceLink(p.source_url, "Inspect OpenStreetMap feature")}</div>`
  );
}
export function boundaryView(feature, editing = false, isDraft = false) {
  const props = feature.properties,
    ha = turf.area(feature) / 10000,
    coords = turf.centerOfMass(feature).geometry.coordinates;
  return (
    head(
      isDraft ? "NEW BOUNDARY" : "SAVED BOUNDARY",
      props.name || "Untitled site",
      "Exact GeoJSON geometry · local research draft",
      "polygon",
      tag("User drawn · unverified", true),
    ) +
    `<div class="detail-body"><div class="metric-grid"><div class="metric"><strong>${fmt(ha)}</strong><span>hectares · spherical area</span></div><div class="metric"><strong>${fmt(ha * 2.47105381)}</strong><span>acres</span></div></div><form id="boundary-form"><label class="form-field">Site name<input id="boundary-name" maxlength="120" required value="${esc(props.name)}" placeholder="e.g. Bhopal north campus"></label><label class="form-field">Boundary type<select id="boundary-kind"><option value="candidate" ${props.kind !== "existing" ? "selected" : ""}>Candidate site</option><option value="existing" ${props.kind === "existing" ? "selected" : ""}>Existing facility footprint (unverified)</option></select></label><label class="form-field">Research notes<textarea id="boundary-notes" maxlength="2000" placeholder="What should be verified here?">${esc(props.notes || "")}</textarea></label><div class="actions"><button class="button primary" type="submit">${icon("check")}${isDraft ? "Save boundary" : "Save changes"}</button><button class="button" type="button" data-action="edit-boundary">${icon("edit")}${editing ? "Finish editing" : "Edit vertices"}</button></div></form><div class="actions">${button("export-boundary", "Export GeoJSON", "download")}${button("delete-boundary", isDraft ? "Discard" : "Delete", "close")}</div><div class="detail-section"><h3>ANALYZE THIS BOUNDARY</h3><p>Export the GeoJSON, then run this in your project folder. The exact geometry is preserved. Current adapters still measure around a representative point; polygon-wide risk checks require further work.</p><pre class="command">uv run dcgeo analyze --boundary boundary.geojson --profile hyperscale_training</pre></div><dl class="facts"><div><dt>Area centroid · latitude, longitude</dt><dd><code>${coords[1].toFixed(6)}, ${coords[0].toFixed(6)}</code></dd></div><div><dt>Boundary assurance</dt><dd>Draft only. Imagery tracing is not a land survey or proof of ownership.</dd></div></dl></div>`
  );
}
export function pointView(latlng, data) {
  const inside =
    latlng.lat >= 23.08 &&
    latlng.lat <= 23.48 &&
    latlng.lng >= 77.18 &&
    latlng.lng <= 77.65;
  const substations = data.overlays.features.filter(
    (f) => f.properties.category === "substation",
  );
  const nearest =
    inside && substations.length
      ? substations
          .map((f) => ({
            feature: f,
            distance: turf.distance(
              turf.point([latlng.lng, latlng.lat]),
              turf.point(f.properties.reference_point),
            ),
          }))
          .sort((a, b) => a.distance - b.distance)[0]
      : null;
  return (
    head(
      "EXPLORE THIS LOCATION",
      "A closer look",
      `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`,
      "pin",
      tag("Not analyzed", true),
    ) +
    `<div class="detail-body">${nearest ? `<div class="metric-grid"><div class="metric"><strong>${fmt(nearest.distance)}</strong><span>km to mapped substation centroid</span></div><div class="metric"><strong>—</strong><span>spare capacity unknown</span></div></div><p class="notice">Straight-line distance computed from the selected point and OpenStreetMap geometry. It does not establish a connection route or available power.</p>${sourceLink(nearest.feature.properties.source_url, "Inspect nearest mapped substation")}` : '<div class="notice">No local infrastructure snapshot covers this point. Missing coverage is not evidence of missing infrastructure.</div>'}<div class="actions">${button("satellite-point", "Satellite", "satellite")}${button("draw", "Draw boundary", "polygon", true)}</div><div class="detail-section"><h3>INVESTIGATE BEFORE SCORING</h3><p>Start with the site outline, then establish the power connection, land title, zoning and water constraints. No suitability score has been assigned to this point.</p></div></div>`
  );
}
export function sourcesView(data) {
  return (
    head(
      "DATA & METHODOLOGY",
      "Know what the map knows",
      "Every layer has a source, a scope and a limit.",
      "layers",
    ) +
    `<div class="detail-body"><div class="source-card"><h4>Facility directory · India</h4><p>PeeringDB public facility records, plus attributed MPSEDC and CtrlS references. ${data.facilities.filter(located).length} located records. ${data.meta?.excluded_coordinates || 0} directory records excluded for missing or out-of-range coordinates. The directory is not a complete census; records may share a campus.</p>${sourceLink(data.meta?.facility_source, "PeeringDB source")}${sourceLink(data.meta?.facility_license, "PeeringDB data policy")}</div><div class="source-card"><h4>Infrastructure · Bhopal pilot</h4><p>OpenStreetMap snapshot: ${esc(data.meta?.osm_retrieved?.slice(0, 10) || "unavailable")}. Power lines, substations, water bodies and industrial land use. ${data.meta?.excluded_geometries || 0} unsupported or invalid geometries omitted. OSM coverage is incomplete and cannot establish capacity or legal rights.</p>${sourceLink("https://www.openstreetmap.org/copyright", "OSM contributors · ODbL")}</div><div class="source-card"><h4>Facility density · India</h4><p>Equal-weight heat kernel over located facility records. Color shows relative directory concentration, not MW, demand or return. Announced facilities without verified coordinates are excluded. This heatmap uses the full inventory, independently of search filters.</p></div><div class="source-card"><h4>Power proximity · Bhopal</h4><p>Tier D derived display model. Sample spacing: 2 km. Intensity = max(0, 1 − distance to nearest mapped substation centroid / 10 km). The fade distance is a display choice. Extent edges can be biased by missing outside features. It does not test voltage, spare capacity or connection rights.</p></div><div class="source-card"><h4>Basemaps & imagery</h4><p>OpenStreetMap, Esri World Imagery and OpenTopoMap. Imagery dates and resolution vary. Zooming beyond native imagery resolution adds no survey accuracy.</p></div><div class="source-card"><h4>Source failure behavior</h4><p>The app reads committed snapshots; opening a map never triggers a facility API or an infrastructure query. A failed refresh leaves the last complete snapshot intact. Missing data is labeled, and saved boundaries remain available.</p></div><div class="source-card"><h4>Investment suitability</h4><p>Not yet a national map layer. The existing 59-factor engine needs evidence for capacity, hazards, water, land and regulation. Its current reports remain available below.</p><a class="text-link" href="diligence.html">Open diligence reports ${icon("arrow")}</a></div></div>`
  );
}

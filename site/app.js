/* datacenter-geo — decision console.
   Reads the build-time payload in data/sites.json. No API calls, no server, no
   keys. Drawing an area computes geometry in the browser and hands you a command
   to run; nothing on this page can trigger a data-source call, which is what
   keeps it free to host and impossible to abuse. */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const TIER_ORDER = ["A", "B", "C", "D", "unknown"];

const DECISION_CLASS = (d) =>
  /NO-GO/i.test(d) ? "d-nogo"
  : /NOT PROVEN/i.test(d) ? "d-notproven"
  : /CONDITIONS/i.test(d) ? "d-cond" : "d-go";

const DECISION_COLOR = (d) =>
  /NO-GO/i.test(d) ? "var(--fail)"
  : /NOT PROVEN/i.test(d) ? "var(--cond)"
  : /CONDITIONS/i.test(d) ? "var(--info)" : "var(--pass)";

/* Factor units are machine identifiers. This page is read by people who do not
   have the factor specs open, so they get rendered as human units. */
const UNIT_LABEL = {
  hours_above_24C_wetbulb: "h/yr above 24 °C wet-bulb",
  free_cooling_hours_per_year: "h/yr free cooling",
  delta_C_design_day_2050: "°C warmer by 2050",
  index_0_100: "/ 100", index_100_baseline: "index (100 = baseline)",
  percent_slope: "% slope", hectares: "ha",
  km_to_wwtp: "km to treatment plant", km_to_qualified_route: "km",
  km_to_capable_port_or_rail: "km", count_distinct_paths: "paths",
  count_carriers: "carriers", ms_rtt_p50: "ms round-trip",
  return_period_years: "-year floodplain", g_pga_475yr: "g peak ground accel.",
  gCO2e_per_kWh: "gCO₂e/kWh", "USD/MWh": "$/MWh",
  USD_per_hectare: "$/ha", USD_per_kW_year: "$/kW-yr",
  SAIDI_minutes_per_year: "min/yr outage",
  flashes_per_km2_per_year: "flashes/km²/yr",
  pm25_annual_ugm3: "µg/m³ PM2.5", m3_per_day: "m³/day",
  design_wind_speed_ms: "m/s design wind",
  months: "months", years: "years", MVA: "MVA", MW: "MW", km: "km",
  ratio: "", category: "",
};
const unit = (u) => (u in UNIT_LABEL ? UNIT_LABEL[u] : String(u || "").replace(/_/g, " "));

const num = (n) =>
  typeof n === "number"
    ? (Math.abs(n) >= 1000 ? n.toLocaleString("en-US", { maximumFractionDigits: 0 })
                           : n.toLocaleString("en-US", { maximumFractionDigits: 2 }))
    : esc(n);

const state = {
  data: null,
  profile: null,
  active: null,        // run_id shown in the panel
  compare: false,
  picked: new Set(),   // run_ids selected for comparison
  evFilter: "all",
  map: null,
  markers: {},
  aoi: null,           // {kind, bounds|latlngs|center+radius, layer}
  draw: null,          // active draw mode
};

/* ── boot ──────────────────────────────────────────────────────────────── */
fetch("data/sites.json")
  .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
  .then((d) => { state.data = d; boot(); })
  .catch((e) => {
    $("panel").innerHTML =
      `<div class="empty" style="color:var(--fail)">Could not load site data: ${esc(e.message)}</div>`;
  });

function boot() {
  state.profile = Object.keys(state.data.meta.profiles)[0];
  renderProfileSeg();
  renderMap();
  renderSiteBar();
  renderLadder();
  renderCoverageLine();
  wireTools();
  wireCompareButton();
  select(state.data.sites[0]?.run_id);
  const g = state.data.generated ? new Date(state.data.generated) : null;
  if (g) $("gen").textContent = "data generated " + g.toISOString().slice(0, 10);
}

/* ── profile selector ──────────────────────────────────────────────────── */
function renderProfileSeg() {
  const P = state.data.meta.profiles;
  $("profile-seg").innerHTML = Object.entries(P).map(([k, v]) =>
    `<button role="tab" data-p="${esc(k)}" aria-selected="${k === state.profile}">${esc(v.label)}</button>`
  ).join("");
  $("profile-seg").onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state.profile = b.dataset.p;
    renderProfileSeg();
    renderSiteBar();
    repaintMarkers();
    render();
  };
  $("profile-note").textContent = P[state.profile]?.description || "";
}

/* ── map ───────────────────────────────────────────────────────────────── */
function renderMap() {
  const m = L.map("map", {
    scrollWheelZoom: false, worldCopyJump: true, zoomControl: true,
  }).setView([28, 20], 2);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 14,
  }).addTo(m);
  // Scroll-to-zoom stays off until the map is clicked, so the page still scrolls
  // past it; clicking in hands over the wheel, which is what people expect.
  m.on("click", () => { if (!state.draw) m.scrollWheelZoom.enable(); });
  m.on("mouseout", () => m.scrollWheelZoom.disable());
  state.map = m;
  paintSites();
}

function paintSites() {
  state.data.sites.forEach((s) => {
    const b = brief(s);
    const mk = L.circleMarker([s.lat, s.lon], {
      radius: 8, color: "#fff", weight: 2,
      fillColor: DECISION_COLOR(b?.decision || ""), fillOpacity: 0.95,
    }).addTo(state.map);
    mk.bindTooltip(`${s.name} — ${b?.decision || "—"}`, { direction: "top" });
    mk.on("click", (e) => {
      L.DomEvent.stopPropagation(e);
      state.compare ? togglePick(s.run_id) : select(s.run_id);
    });
    state.markers[s.run_id] = mk;
  });
}

function repaintMarkers() {
  state.data.sites.forEach((s) => {
    const mk = state.markers[s.run_id];
    if (!mk) return;
    const b = brief(s);
    mk.setStyle({ fillColor: DECISION_COLOR(b?.decision || "") });
    mk.setTooltipContent(`${s.name} — ${b?.decision || "—"}`);
  });
}

/* ── drawing: rectangle, polygon, radius ────────────────────────────────
   Hand-rolled rather than pulled from a plugin. The whole interaction is under
   a hundred lines, it produces exactly the geometry the CLI takes, and it keeps
   the page down to one third-party script. */
const SHAPE = { color: "#1F5D4C", weight: 2, fillOpacity: 0.12, dashArray: "5 4" };

function wireTools() {
  document.querySelectorAll(".maptools button").forEach((b) => {
    b.onclick = () => setDraw(b.dataset.draw === state.draw ? null : b.dataset.draw);
  });
  SHAPE.color =
    getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#1F5D4C";

  const m = state.map;
  let start = null, temp = null, pts = [];

  m.on("mousedown", (e) => {
    if (state.draw !== "rect" && state.draw !== "circle") return;
    m.dragging.disable();
    start = e.latlng;
    if (temp) m.removeLayer(temp);
    temp = state.draw === "rect"
      ? L.rectangle([start, start], SHAPE).addTo(m)
      : L.circle(start, { ...SHAPE, radius: 1 }).addTo(m);
  });

  m.on("mousemove", (e) => {
    if (!start || !temp) return;
    if (state.draw === "rect") temp.setBounds(L.latLngBounds(start, e.latlng));
    else temp.setRadius(start.distanceTo(e.latlng));
  });

  m.on("mouseup", (e) => {
    if (!start || !temp) return;
    m.dragging.enable();
    const kind = state.draw;
    const radius = start.distanceTo(e.latlng);
    // A click with no drag is not an area. Discard it rather than publishing a
    // zero-hectare AOI that looks like a measurement.
    if ((kind === "circle" && radius < 50) ||
        (kind === "rect" && start.distanceTo(e.latlng) < 50)) {
      m.removeLayer(temp);
      start = null; temp = null;
      return;
    }
    commit(kind === "rect"
      ? { kind: "rect", layer: temp, bounds: L.latLngBounds(start, e.latlng) }
      : { kind: "circle", layer: temp, center: start, radius });
    start = null; temp = null;
    setDraw(null);
  });

  m.on("click", (e) => {
    if (state.draw !== "poly") return;
    pts.push(e.latlng);
    if (temp) m.removeLayer(temp);
    temp = L.polygon(pts, SHAPE).addTo(m);
    hint(`${pts.length} point${pts.length === 1 ? "" : "s"} — double-click to close`);
  });

  m.on("dblclick", () => {
    if (state.draw !== "poly" || pts.length < 3) return;
    commit({ kind: "poly", layer: temp, latlngs: pts.slice() });
    pts = []; temp = null;
    setDraw(null);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (temp) { m.removeLayer(temp); temp = null; }
    start = null; pts = [];
    setDraw(null);
  });
}

function setDraw(mode) {
  if (mode === "clear") return clearAOI();
  state.draw = mode;
  document.querySelectorAll(".maptools button").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.draw === mode)));
  $("map").classList.toggle("drawing", !!mode);
  state.map.doubleClickZoom[mode === "poly" ? "disable" : "enable"]();
  hint(mode === "rect" ? "Drag to draw a rectangle · Esc to cancel"
    : mode === "poly" ? "Click to add points, double-click to close · Esc to cancel"
    : mode === "circle" ? "Drag out from the centre point · Esc to cancel"
    : null);
}

function hint(text) {
  const h = $("maphint");
  h.hidden = !text;
  if (text) h.textContent = text;
}

function clearAOI() {
  if (state.aoi?.layer) state.map.removeLayer(state.aoi.layer);
  state.aoi = null;
  $("aoi").hidden = true;
  state.draw = null;
  document.querySelectorAll(".maptools button").forEach((b) =>
    b.setAttribute("aria-pressed", "false"));
  $("map").classList.remove("drawing");
  hint(null);
}

function commit(aoi) {
  if (state.aoi?.layer) state.map.removeLayer(state.aoi.layer);
  aoi.layer.setStyle({ ...SHAPE, dashArray: null });
  state.aoi = aoi;
  renderAOI();
}

/* Spherical-excess area. Labelled as an approximation on the card, because it is
   one — it ignores the ellipsoid, which matters at the third significant figure
   and not at the decision this number feeds. */
const R = 6371008.8;
const rad = (d) => (d * Math.PI) / 180;

function polygonAreaM2(ring) {
  if (ring.length < 3) return 0;
  let sum = 0;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i], b = ring[(i + 1) % ring.length];
    sum += (rad(b.lng) - rad(a.lng)) * (2 + Math.sin(rad(a.lat)) + Math.sin(rad(b.lat)));
  }
  return Math.abs((sum * R * R) / 2);
}

function aoiGeometry() {
  const a = state.aoi;
  if (!a) return null;
  if (a.kind === "circle") {
    return {
      centre: a.center, areaM2: Math.PI * a.radius * a.radius,
      radiusKm: a.radius / 1000, shape: "radius",
    };
  }
  const ring = a.kind === "rect"
    ? (() => {
        const b = a.bounds;
        return [b.getSouthWest(), b.getNorthWest(), b.getNorthEast(), b.getSouthEast()];
      })()
    : a.latlngs;
  const centre = ring.reduce(
    (acc, p) => ({ lat: acc.lat + p.lat / ring.length, lng: acc.lng + p.lng / ring.length }),
    { lat: 0, lng: 0 });
  const areaM2 = polygonAreaM2(ring);
  return {
    centre, areaM2, shape: a.kind === "rect" ? "rectangle" : "polygon",
    // The radius that makes a circle of equal area, which is what the CLI takes.
    radiusKm: Math.sqrt(areaM2 / Math.PI) / 1000,
    // `dcgeo scan` takes south,west,north,east directly — pass the real extent
    // rather than a circle fitted to it, which would cover different ground.
    bbox: a.kind === "rect"
      ? [a.bounds.getSouth(), a.bounds.getWest(), a.bounds.getNorth(), a.bounds.getEast()]
      : null,
  };
}

/* An AOI the size of a county is not a site, and offering to `analyze` it as one
   would produce a confident answer about a centroid nobody chose. Past this
   radius the honest command is `scan`, which tiles a region and ranks candidates
   — which is the tool that actually exists for the thing that was drawn. */
const SITE_MAX_RADIUS_KM = 25;

function renderAOI() {
  const g = aoiGeometry();
  if (!g) return;
  const ha = g.areaM2 / 10000;
  const lat = g.centre.lat.toFixed(4), lon = g.centre.lng.toFixed(4);
  const isRegion = g.radiusKm > SITE_MAX_RADIUS_KM;

  // Area in the unit that reads: hectares for a parcel, km² once it is a region.
  const area = ha >= 100000
    ? `${num(Math.round(g.areaM2 / 1e6))} <small>km²</small>`
    : `${num(Math.round(ha))} <small>ha</small>`;

  const cmd = isRegion
    ? (g.bbox
        ? `uv run dcgeo scan --bbox ${g.bbox.map((v) => v.toFixed(3)).join(",")}`
        : `uv run dcgeo scan --at ${lat},${lon} --radius ${g.radiusKm.toFixed(0)}`)
    : `uv run dcgeo analyze --at ${lat},${lon} --radius ${g.radiusKm.toFixed(1)} --profile ${state.profile}`;

  // The hyperscale training profile declares an 80 ha floor and a 200 ha typical.
  // Stating the drawn area against those turns a raw number into something the
  // reader can act on without opening the factor specs — but only at a scale
  // where the comparison means anything.
  const test = isRegion
    ? ["a region, not a site — prospect it for candidates", "var(--info)"]
    : ha >= 200 ? ["fits a typical 200 ha training campus", "var(--pass)"]
    : ha >= 80 ? ["clears the 80 ha floor, under the 200 ha typical", "var(--cond)"]
    : ["under the 80 ha floor for a training campus", "var(--fail)"];

  const issue = state.data.meta.repo + "/issues/new?" + new URLSearchParams({
    title: `${isRegion ? "Scan" : "Analysis"} request — ${lat}, ${lon}`,
    labels: isRegion ? "scan-request" : "analysis-request",
    body: [
      "**Area of interest**", "",
      `- Shape: ${g.shape}`,
      `- Centroid: ${lat}, ${lon}`,
      `- Area: ${Math.round(ha).toLocaleString("en-US")} ha (spherical approximation)`,
      `- Equivalent radius: ${g.radiusKm.toFixed(1)} km`,
      ...(g.bbox ? [`- Bounding box: ${g.bbox.map((v) => v.toFixed(4)).join(", ")}`] : []),
      ...(isRegion ? [] : [`- Profile: ${state.profile}`]),
      "", "**Command**", "", "```bash", cmd, "```", "",
      "<!-- Drawn on the datacenter-geo map. Geometry was computed in the browser;",
      "     no data source was called to produce it. -->",
    ].join("\n"),
  }).toString();

  $("aoi").hidden = false;
  $("aoi").innerHTML = `
    <h4>Area of interest — drawn, not analyzed</h4>
    <dl class="geom">
      <div><dt>Area</dt><dd>${area}</dd></div>
      <div><dt>Centroid</dt><dd style="font-size:14px">${lat}, ${lon}</dd></div>
      <div><dt>Equiv. radius</dt><dd>${g.radiusKm < 10 ? g.radiusKm.toFixed(1) : num(Math.round(g.radiusKm))} <small>km</small></dd></div>
      <div><dt>Scale</dt><dd style="font-size:13px;color:${test[1]}">${esc(test[0])}</dd></div>
    </dl>
    <pre>${esc(cmd)}</pre>
    <div class="acts">
      <button class="ghost" id="copycmd">Copy command</button>
      <a class="ghost" href="${esc(issue)}" target="_blank" rel="noopener"
         style="text-decoration:none;display:inline-block">Request ${isRegion ? "a scan" : "an analysis"}</a>
      <button class="ghost" id="clearaoi">Clear</button>
    </div>
    <p class="why">Area is a spherical approximation of the drawn shape — no data source
      was called to produce it, and this is not an analysis.
      ${isRegion
        ? `At this size the centroid is not a site, so the command above is
           <code>scan</code>, which tiles the region and ranks candidates, rather than
           <code>analyze</code>, which would answer confidently about a point nobody chose.`
        : ""}
      Running the command calls live APIs from your machine against your own rate limits.
      The request link opens a GitHub issue, which is where a third-party request gets
      triaged by a person rather than executed silently by this page.</p>`;

  $("copycmd").onclick = async (e) => {
    try { await navigator.clipboard.writeText(cmd); e.target.textContent = "Copied"; }
    catch { e.target.textContent = "Select the text above"; }
    setTimeout(() => (e.target.textContent = "Copy command"), 1800);
  };
  $("clearaoi").onclick = clearAOI;
}

/* ── site chips ────────────────────────────────────────────────────────── */
const brief = (s) => s.briefs?.[state.profile];

function renderSiteBar() {
  $("sitebar").innerHTML = state.data.sites.map((s) => {
    const b = brief(s), p = s.profiles[state.profile];
    return `<button class="sitechip" role="listitem" data-run="${esc(s.run_id)}">
      <span class="dot" style="background:${DECISION_COLOR(b?.decision || "")}"></span>
      <span><span class="nm">${esc(s.name.split(/[,(]/)[0].trim())}</span>
      <span class="sc">${p?.score ?? "—"} ± ${p?.band ?? "—"}</span></span>
    </button>`;
  }).join("");
  $("sitebar").onclick = (e) => {
    const b = e.target.closest(".sitechip");
    if (!b) return;
    state.compare ? togglePick(b.dataset.run) : select(b.dataset.run);
  };
  syncChips();
}

function syncChips() {
  document.querySelectorAll(".sitechip").forEach((b) => {
    b.setAttribute("aria-current", String(!state.compare && b.dataset.run === state.active));
    b.classList.toggle("picked", state.compare && state.picked.has(b.dataset.run));
  });
}

function select(runId) {
  if (!runId) return;
  state.active = runId;
  const mk = state.markers[runId];
  if (mk) state.map.panTo(mk.getLatLng(), { animate: true });
  syncChips();
  render();
}

function togglePick(runId) {
  state.picked.has(runId) ? state.picked.delete(runId) : state.picked.add(runId);
  syncChips();
  render();
}

function wireCompareButton() {
  const btn = $("compare-btn");
  btn.onclick = () => {
    state.compare = !state.compare;
    btn.setAttribute("aria-pressed", String(state.compare));
    btn.textContent = state.compare ? "Back to one site" : "Compare sites";
    if (state.compare && state.picked.size === 0) {
      state.data.sites.slice(0, 2).forEach((s) => state.picked.add(s.run_id));
    }
    syncChips();
    render();
  };
}

/* ── render ────────────────────────────────────────────────────────────── */
function render() {
  state.compare ? renderCompare() : renderDecision();
}

function renderDecision() {
  const s = state.data.sites.find((x) => x.run_id === state.active);
  if (!s) return;
  const b = brief(s);
  if (!b) { $("panel").innerHTML = `<div class="empty">No brief for this profile.</div>`; return; }

  const place = [s.admin2, s.admin1, s.country].filter(Boolean).join(" · ");
  const dark = Object.entries(b.domain_coverage).filter(([, c]) => !c.in_score).map(([d]) => d);

  $("panel").innerHTML = `
    <div class="phead">
      <span class="decision ${DECISION_CLASS(b.decision)}">${esc(b.decision)}</span>
      <h3>${esc(s.name)}</h3>
      <div class="where">${esc(place)}${s.market ? " · " + esc(s.market) : ""} ·
        ${s.lat.toFixed(4)}, ${s.lon.toFixed(4)} · ${esc(s.run_id)}</div>
      <p class="answer">${esc(b.headline)}</p>
    </div>

    <dl class="metrics">
      <div><dt>Score</dt><dd>${b.score ?? "—"} <small>± ${b.band ?? "—"}</small></dd></div>
      <div><dt>Confidence</dt><dd>${b.confidence.toFixed(2)}</dd></div>
      <div><dt>Decision weight measured</dt><dd>${Math.round(b.measured_fraction * 100)}<small>%</small></dd></div>
      <div><dt>Cooling assumed</dt><dd style="font-size:14px">${esc(s.cooling_assumption || "—")}</dd></div>
    </dl>

    ${sectionBlockers(b)}
    ${sectionSwings(b)}
    ${sectionQueue(b)}
    ${sectionDomains(b, dark)}
    ${sectionEvidence(s)}
  `;
  wirePanel(s);
}

function sectionBlockers(b) {
  const c = b.blocker_counts;
  const shown = b.blockers.length;
  const total = c.fatal + c.major + c.minor;
  if (!shown) return "";
  return `<section class="psec">
    <h4>Decision blockers <span class="count">${c.fatal} fatal · ${c.major} major · ${c.minor} minor</span></h4>
    <p class="sublede">What stands between this evidence and a decision. Ranked by
      severity, then by the score points each puts at risk. Every one names the
      counterparty who can close it.</p>
    ${b.blockers.map((x) => `
      <details class="blk ${esc(x.severity)}">
        <summary>
          <span class="sev">${esc(x.severity)}</span>
          <span class="bt">${esc(x.title)}</span>
          <span class="pts">${x.pts ? x.pts.toFixed(0) + " pts" : "—"}</span>
        </summary>
        <div class="body">
          <p>${esc(x.why)}</p>
          <div class="rt"><b>Closes</b><span>${esc(x.resolve)}</span></div>
          <div class="rt"><b>Ask</b><span>${esc(x.owner)}${
            x.weeks ? ` · typically ${x.weeks[0]}–${x.weeks[1]} weeks` : ""}</span></div>
        </div>
      </details>`).join("")}
    ${total > shown ? `<p class="moreblk">+ ${total - shown} more of lower severity —
      the full list is in <code>runs/${esc(state.active)}/report.md</code></p>` : ""}
  </section>`;
}

function sectionSwings(b) {
  const sw = b.swings.filter((x) => x.swing > 0).slice(0, 10);
  if (!sw.length) return "";
  const max = Math.max(...sw.map((x) => x.swing), 1);
  const flips = b.swings.filter((x) => x.flips).length;
  return `<section class="psec">
    <h4>What could flip the verdict <span class="count">${flips} can, on their own</span></h4>
    <p class="sublede">Each row is the scorer re-run with that one factor resolved at its
      best and worst plausible value, everything else held. Amber bars are factors nobody
      has measured — the verdict currently rests on guessing them correctly.</p>
    ${sw.map((x) => `
      <div class="swing ${x.known ? "kn" : "unk"}">
        <span class="sn">${esc(x.name)}
          ${x.gate ? '<i class="gate">gate</i>' : ""}
          ${x.flips ? `<i class="flip">${esc(x.worst)} → ${esc(x.best)}</i>` : ""}
          ${x.known ? `<i>tier ${esc(x.tier)}</i>` : "<i>unmeasured</i>"}</span>
        <span class="bar"><i style="width:${Math.max(3, (x.swing / max) * 100)}%"></i></span>
        <span class="sv">±${x.swing.toFixed(1)}</span>
      </div>`).join("")}
  </section>`;
}

function sectionQueue(b) {
  if (!b.queue.length) return "";
  return `<section class="psec">
    <h4>Verify next <span class="count">${b.queue.length} items, in order</span></h4>
    <p class="sublede">Ordered by how much of the decision each answer settles.
      Gate-critical items come first regardless of points, because a knockout check that
      cannot be evaluated can make everything below it irrelevant.</p>
    <ol class="vq">
      ${b.queue.map((v) => `<li>
        <span class="n">${v.rank}</span>
        <div>
          <div class="q">${esc(v.question)}</div>
          <div class="meta">
            ${v.gate ? '<span class="gk">gate-critical</span>' : ""}
            <span>${v.pts.toFixed(1)} pts at risk</span>
            ${v.weeks ? `<span>${v.weeks[0]}–${v.weeks[1]} weeks</span>` : ""}
            <span>${esc(v.factor_id)}</span>
          </div>
          <div class="get"><b>Ask</b>${esc(v.owner)}</div>
          <div class="get"><b>Get</b>${esc(v.artifact)}</div>
          ${v.note ? `<div class="note">${esc(v.note)}</div>` : ""}
        </div>
      </li>`).join("")}
    </ol>
    <div class="acts" style="margin-top:14px">
      <button class="ghost" id="copyq">Copy as a checklist</button></div>
  </section>`;
}

function sectionDomains(b, dark) {
  const rows = Object.entries(b.domain_coverage)
    .sort((a, c) => c[1].domain_weight - a[1].domain_weight);
  return `<section class="psec">
    <h4>Domain coverage ${dark.length
      ? `<span class="count">${dark.length} excluded from the score</span>` : ""}</h4>
    <p class="sublede">${dark.length
      ? `The headline is a weighted mean over the domains that had data — <strong>${
          dark.map(esc).join(", ")}</strong> contributed nothing to it.`
      : "Every domain contributed to the score."}</p>
    <div class="doms">
      ${rows.map(([d, c]) => `<div class="dom ${c.in_score ? "" : "dark"}">
        <span class="dl">${esc(d)}</span>
        <span class="track"><i style="width:${Math.round(c.weight_measured * 100)}%"></i></span>
        <span class="dv">${c.measured}/${c.factors}${
          c.in_score && c.score !== null ? ` · ${Math.round(c.score)}` : " · dark"}</span>
      </div>`).join("")}
    </div>
  </section>`;
}

function sectionEvidence(s) {
  const f = state.evFilter;
  const ms = f === "unknown" ? []
    : s.measurements.filter((m) => f === "all" || f === "measured" || m.tier === f);
  const showUnknown = f === "all" || f === "unknown";
  return `<section class="psec">
    <h4>Evidence <span class="count">${s.measurements.length} measured · ${s.unmeasured.length} unmeasured</span></h4>
    <p class="sublede">Every datapoint with where it came from, when it was retrieved, and
      how much that is worth today. A value past its source's refresh window is marked and
      discounted in the confidence figure above.</p>
    <div class="evfilter">
      ${["all", "measured", "A", "B", "C", "D", "unknown"].map((k) =>
        `<button data-ev="${k}" aria-pressed="${f === k}">${
          k === "all" ? "All" : k === "measured" ? "Measured"
          : k === "unknown" ? "Unmeasured" : "Tier " + k}</button>`).join("")}
    </div>
    ${ms.map((m) => `<div class="ev">
      <span class="en">${esc(m.name)}<span class="eq">${esc(m.question)}</span></span>
      <span class="evl">${num(m.value)}<small>${esc(unit(m.unit))}</small></span>
      <span class="prov">
        <span class="tchip t-${esc(m.tier)}">TIER ${esc(m.tier)}</span>
        ${m.freshness && m.freshness !== "fresh"
          ? `<span class="fchip ${esc(m.freshness)}">${esc(m.freshness)}</span>` : ""}
        <span>${m.source_url
          ? `<a href="${esc(m.source_url)}" target="_blank" rel="noopener">${esc(m.source)}</a>`
          : esc(m.source)}</span>
        <span>retrieved ${esc(m.retrieved)}${
          m.age_days != null ? ` · ${Math.round(m.age_days)}d old` : ""}</span>
        ${m.confidence != null ? `<span>confidence ${m.confidence.toFixed(2)}</span>` : ""}
      </span>
    </div>`).join("")}
    ${showUnknown ? unmeasuredHtml(s) : ""}
  </section>`;
}

function unmeasuredHtml(s) {
  const byDomain = {};
  (s.unmeasured || []).forEach((u) => (byDomain[u.domain] ||= []).push(u));
  const keys = Object.keys(byDomain).sort();
  if (!keys.length) return "";
  return `<div class="unkline" style="margin-top:16px">
    <p style="font-size:13.5px;color:var(--muted);margin:0 0 4px">Listed rather than hidden.
      Each of these widens the ± band above; none is quietly filled with an average. Hover
      for the reason it could not be measured.</p>
    ${keys.map((d) => `<b>${esc(d)} · ${byDomain[d].length}</b>
      ${byDomain[d].map((u) =>
        `<span title="${esc(state.data.reasons?.[u.reason_id] || "")}">${esc(u.name)}</span>`
      ).join(" · ")}`).join("")}
  </div>`;
}

function wirePanel(s) {
  document.querySelectorAll("[data-ev]").forEach((b) => {
    b.onclick = () => { state.evFilter = b.dataset.ev; render(); };
  });
  const cq = $("copyq");
  if (!cq) return;
  cq.onclick = async () => {
    const b = brief(s);
    const text = [
      `Verification queue — ${s.name} (${s.run_id}, ${state.profile})`,
      `Decision: ${b.decision}`, "",
      ...b.queue.map((v) => [
        `[ ] ${v.rank}. ${v.question}`,
        `      factor: ${v.factor_id} · ${v.pts.toFixed(1)} pts at risk${v.gate ? " · GATE-CRITICAL" : ""}`,
        `      ask:    ${v.owner}${v.weeks ? ` (typically ${v.weeks[0]}-${v.weeks[1]} weeks)` : ""}`,
        `      get:    ${v.artifact}`,
      ].join("\n")),
    ].join("\n");
    try { await navigator.clipboard.writeText(text); cq.textContent = "Copied"; }
    catch { cq.textContent = "Copy failed"; }
    setTimeout(() => (cq.textContent = "Copy as a checklist"), 1800);
  };
}

/* ── comparison ────────────────────────────────────────────────────────── */
/* The separability test uses the same rule as dcgeo.compare: a pair whose scores
   differ by less than the mean of their bands is not separable, and an edge only
   exists where both sides measured the same factor. This page has no scorer, so
   it reports measured differences in their own units rather than inventing a
   "better" — direction lives in the factor specs, which are not shipped here. */
function renderCompare() {
  const picked = state.data.sites.filter((s) => state.picked.has(s.run_id));
  if (picked.length < 2) {
    $("panel").innerHTML = `<div class="empty">Pick at least two sites — click the chips
      under the map, or the pins themselves.</div>`;
    return;
  }

  const vals = {};
  picked.forEach((s) => {
    vals[s.run_id] = {};
    s.measurements.forEach((m) => { vals[s.run_id][m.factor_id] = m; });
  });

  const ranked = picked
    .map((s) => ({ s, p: s.profiles[state.profile] }))
    .filter((x) => x.p?.score != null)
    .sort((a, b) => b.p.score - a.p.score);

  const overlaps = [];
  for (let i = 0; i + 1 < ranked.length; i++) {
    const a = ranked[i], b = ranked[i + 1];
    if (Math.abs(a.p.score - b.p.score) < (a.p.band + b.p.band) / 2)
      overlaps.push([a.s.name.split(/[,(]/)[0].trim(), b.s.name.split(/[,(]/)[0].trim()]);
  }
  const separable = overlaps.length === 0 && ranked.length > 1;

  // Factors nobody measured: the questions this comparison assumes away equally
  // for every candidate, which is exactly when an assumption becomes invisible.
  const measuredAnywhere = new Set(picked.flatMap((s) => s.measurements.map((m) => m.factor_id)));
  const blind = (picked[0].unmeasured || [])
    .filter((u) => !measuredAnywhere.has(u.factor_id))
    .filter((u) => picked.every((s) => s.unmeasured.some((x) => x.factor_id === u.factor_id)))
    .slice(0, 12);

  $("panel").innerHTML = `
    <div class="phead">
      <span class="decision ${separable ? "d-go" : "d-notproven"}">
        ${separable ? "SEPARABLE" : "NOT SEPARABLE"}</span>
      <h3>${picked.length} sites — ${esc(state.data.meta.profiles[state.profile].label)}</h3>
      <div class="where">click chips or pins to add and remove sites</div>
    </div>
    <div class="cmp">
      <div class="cmpbanner ${separable ? "yes" : "no"}">${separable
        ? "Every adjacent pair is separated by more than the mean of their ± bands, so this ordering is supported by the evidence."
        : `${overlaps.length} adjacent pair${overlaps.length > 1 ? "s" : ""} overlap within the
           confidence bands (${overlaps.map((o) => esc(o.join(" / "))).join("; ")}).
           <strong>The ordering is not supported by the evidence</strong> — compare them on
           the measured differences below, not on the score.`}</div>

      ${ranked.map(({ s, p }) => cmpSite(s, p, picked, vals)).join("")}

      ${blind.length ? `<div class="blind">
        <h4 style="font-size:12px;letter-spacing:.09em;text-transform:uppercase;
          color:var(--faint);margin-bottom:6px">Shared blind spots</h4>
        <p class="sublede">Unmeasured for every site here, so the comparison assumes them
          away equally. These are the differences it cannot see.</p>
        <div class="unkline">${blind.map((u) => esc(u.name)).join(" · ")}</div>
      </div>` : ""}
    </div>`;
}

function cmpSite(s, p, picked, vals) {
  const b = brief(s);
  const edges = [];
  Object.entries(vals[s.run_id]).forEach(([fid, m]) => {
    const others = picked.filter((o) => o.run_id !== s.run_id && vals[o.run_id][fid]);
    if (!others.length) return;
    const mine = Number(m.value);
    const mean = others.reduce((a, o) => a + Number(vals[o.run_id][fid].value), 0) / others.length;
    if (!isFinite(mine) || !isFinite(mean) || mine === mean) return;
    // Relative gap, so factors on wildly different scales rank against each other.
    const rel = Math.abs(mine - mean) / (Math.abs(mean) || 1);
    edges.push({ name: m.name, unit: m.unit, mine, mean, d: mine - mean, rel });
  });
  edges.sort((a, c) => c.rel - a.rel);

  return `<div class="cmpsite">
    <h5>${esc(s.name)}</h5>
    <div class="cs">${esc(b?.decision || "—")} · ${p.score} ± ${p.band} ·
      ${Math.round(p.measured_fraction * 100)}% measured · ${
        esc([s.admin1, s.country].filter(Boolean).join(", "))}</div>
    ${edges.slice(0, 6).map((e) => `<div class="edge ${e.d > 0 ? "w" : "l"}">
      <span class="s">${e.d > 0 ? "▲" : "▼"}</span>
      <span class="en">${esc(e.name)}
        <span style="color:var(--faint);font-size:11.5px">${num(e.mine)} vs ${
          num(Math.round(e.mean * 100) / 100)} ${esc(unit(e.unit))} across the others</span></span>
      <span class="ed">${e.d > 0 ? "+" : ""}${num(Math.round(e.d * 100) / 100)}</span>
    </div>`).join("") || `<p class="sublede">No factor is measured on both sides.</p>`}
    ${b?.blockers?.length ? `<div class="edge" style="margin-top:8px">
      <span class="s" style="color:var(--fail)">!</span>
      <span class="en" style="font-size:13px;color:var(--muted)">Top blocker:
        ${esc(b.blockers[0].title)}</span><span class="ed"></span></div>` : ""}
  </div>`;
}

/* ── static bits ───────────────────────────────────────────────────────── */
function renderLadder() {
  const tc = state.data.meta.tier_counts;
  const total = Object.values(tc).reduce((a, b) => a + b, 0) || 1;
  $("ladder").innerHTML = TIER_ORDER.map((t) => {
    const n = tc[t] || 0;
    if (!n) return "";
    const pct = (n / total) * 100;
    const label = pct > 7 ? `${t === "unknown" ? "UNKNOWN" : "TIER " + t} ${n}` : (pct > 3 ? t : "");
    return `<span style="width:${pct}%;background:var(--t${t === "unknown" ? "U" : t});
      ${t === "unknown" ? "color:var(--ink-2)" : ""}" title="${t}: ${n}">${label}</span>`;
  }).join("");
}

function renderCoverageLine() {
  const tc = state.data.meta.tier_counts;
  const measured = TIER_ORDER.filter((t) => t !== "unknown").reduce((a, t) => a + (tc[t] || 0), 0);
  const total = Object.values(tc).reduce((a, b) => a + b, 0);
  $("cov-line").innerHTML = `only <strong>${measured} of ${total}</strong> factor slots are
    filled — about <strong>${Math.round((measured / total) * 100)}%</strong> coverage`;
}

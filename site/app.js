/* datacenter-geo — static site.
   Reads the build-time payload in data/sites.json. No API calls, no server. */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const VERDICT_CLASS = (v) =>
  /NO-GO/i.test(v) ? "b-fail" : /strong|viable/i.test(v) ? "b-pass" : "b-cond";

const TIER_ORDER = ["A", "B", "C", "D", "unknown"];
/* Factor units are machine identifiers. This page is for readers who do not have
   the factor specs open, so they get rendered as human units. */
const UNIT_LABEL = {
  hours_above_24C_wetbulb: "h/yr above 24\u202F\u00B0C wet-bulb",
  free_cooling_hours_per_year: "h/yr free cooling",
  delta_C_design_day_2050: "\u00B0C warmer by 2050",
  index_0_100: "/ 100",
  percent_slope: "% slope",
  hectares: "ha",
  km_to_wwtp: "km to treatment plant",
  km_to_qualified_route: "km",
  km_to_capable_port_or_rail: "km",
  count_distinct_paths: "paths",
  count_carriers: "carriers",
  ms_rtt_p50: "ms round-trip",
  return_period_years: "-year floodplain",
  g_pga_475yr: "g peak ground accel.",
  gCO2e_per_kWh: "gCO\u2082e/kWh",
  "USD/MWh": "$/MWh",
  USD_per_hectare: "$/ha",
  USD_per_kW_year: "$/kW-yr",
  SAIDI_minutes_per_year: "min/yr outage",
  flashes_per_km2_per_year: "flashes/km\u00B2/yr",
  pm25_annual_ugm3: "\u00B5g/m\u00B3 PM2.5",
  m3_per_day: "m\u00B3/day",
  design_wind_speed_ms: "m/s design wind",
  months: "months",
  years: "years",
  MVA: "MVA",
  MW: "MW",
  km: "km",
  ratio: "",
  category: "",
};
const prettyUnit = (u) => (u in UNIT_LABEL ? UNIT_LABEL[u] : String(u || "").replace(/_/g, " "));

const fmtNum = (n) =>
  typeof n === "number"
    ? (Math.abs(n) >= 1000 ? n.toLocaleString("en-US", { maximumFractionDigits: 0 })
                           : n.toLocaleString("en-US", { maximumFractionDigits: 2 }))
    : esc(n);

let DATA = null;
let MAP = null;
let MARKERS = {};
let ACTIVE = null;

/* ---------- boot ---------- */
fetch("data/sites.json")
  .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
  .then((d) => { DATA = d; render(); })
  .catch((e) => {
    document.getElementById("sitelist").innerHTML =
      `<div style="padding:20px;color:var(--fail)">Could not load site data: ${esc(e.message)}</div>`;
  });

function render() {
  renderStats();
  renderMap();
  renderList();
  renderChart();
  renderLadder();
  select(DATA.sites[0]?.run_id);
  const g = DATA.generated ? new Date(DATA.generated) : null;
  if (g) document.getElementById("gen").textContent =
    "data generated " + g.toISOString().slice(0, 10);
}

/* ---------- header stats ---------- */
function renderStats() {
  const m = DATA.meta;
  const measured = TIER_ORDER.filter((t) => t !== "unknown")
    .reduce((a, t) => a + (m.tier_counts[t] || 0), 0);
  const total = Object.values(m.tier_counts).reduce((a, b) => a + b, 0);
  const rows = [
    ["Sites analyzed", DATA.sites.length],
    ["Factors", m.factor_count],
    ["Data sources", m.source_count],
    ["Need no API key", m.keyless_source_count],
    ["Measurements taken", measured],
  ];
  document.getElementById("stats").innerHTML = rows
    .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd class="num">${v}</dd></div>`).join("");
  document.getElementById("hero-src").textContent = `${m.source_count} data sources`;

  const pct = total ? Math.round((measured / total) * 100) : 0;
  document.getElementById("cov-line").innerHTML =
    `only <strong>${measured} of ${total}</strong> factor slots are filled — about
     <strong>${pct}%</strong> coverage`;
}

/* ---------- map ---------- */
function renderMap() {
  MAP = L.map("map", { scrollWheelZoom: false, worldCopyJump: true }).setView([25, 40], 2);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 12,
  }).addTo(MAP);

  DATA.sites.forEach((s) => {
    const p = s.profiles.hyperscale_training || Object.values(s.profiles)[0];
    const col = /NO-GO/i.test(p.verdict) ? "#9E3A28"
      : /strong|viable/i.test(p.verdict) ? "#3C7A5E" : "#9C7016";
    const mk = L.circleMarker([s.lat, s.lon], {
      radius: 8, className: "pin", color: "#fff", weight: 2,
      fillColor: col, fillOpacity: 0.95,
    }).addTo(MAP);
    mk.bindTooltip(`${s.name} — ${p.score ?? "—"}`, { direction: "top" });
    mk.on("click", () => select(s.run_id));
    MARKERS[s.run_id] = mk;
  });
}

/* ---------- site list ---------- */
function renderList() {
  document.getElementById("sitelist").innerHTML = DATA.sites.map((s) => {
    const p = s.profiles.hyperscale_training || Object.values(s.profiles)[0];
    const place = [s.admin2, s.admin1, s.country].filter(Boolean).join(" · ");
    return `<button class="siterow" role="listitem" data-run="${esc(s.run_id)}">
      <span class="r1"><span class="nm">${esc(s.name)}</span>
        <span class="sc">${p.score ?? "—"} ± ${p.band ?? "—"}</span></span>
      <span class="r2">${esc(place)}</span>
    </button>`;
  }).join("");
  document.getElementById("sitelist").addEventListener("click", (e) => {
    const b = e.target.closest(".siterow");
    if (b) select(b.dataset.run);
  });
}

/* ---------- detail ---------- */
function select(runId) {
  if (!runId) return;
  ACTIVE = runId;
  const s = DATA.sites.find((x) => x.run_id === runId);
  if (!s) return;

  document.querySelectorAll(".siterow").forEach((b) =>
    b.setAttribute("aria-current", String(b.dataset.run === runId)));
  if (MARKERS[runId]) MAP.panTo(MARKERS[runId].getLatLng(), { animate: true });

  const place = [s.admin2, s.admin1, s.country].filter(Boolean).join(" · ");
  const verdictCards = Object.entries(s.profiles).map(([k, p]) => {
    const label = DATA.meta.profiles[k]?.label || k;
    return `<div class="vcard">
      <div class="pl">${esc(label)}</div>
      <div class="vv"><span class="badge ${VERDICT_CLASS(p.verdict)}">${esc(p.verdict)}</span></div>
      <div class="ss">${p.score ?? "—"} <span style="font-size:13px;color:var(--muted)">± ${p.band ?? "—"}</span></div>
      <div class="cf">confidence ${p.confidence} · ${Math.round((p.measured_fraction || 0) * 100)}% measured</div>
    </div>`;
  }).join("");

  const prof = s.profiles.hyperscale_training || Object.values(s.profiles)[0];
  const doms = Object.entries(prof.domain_scores || {})
    .filter(([, v]) => v !== null)
    .sort((a, b) => b[1] - a[1])
    .map(([d, v]) => `<div class="dbar">
      <span class="lbl">${esc(d)}</span>
      <span class="track"><i style="width:${Math.max(2, v)}%"></i></span>
      <span class="v">${v.toFixed(0)}</span></div>`).join("");

  const heads = s.measurements.filter((m) => m.headline && m.value !== null);
  const measured = heads.length ? heads.map((m) => `<div class="mrow">
      <span class="mn">${esc(m.name)}<span class="mq">${esc(m.question)}</span></span>
      <span class="mv">${fmtNum(m.value)}<span class="mu">${esc(prettyUnit(m.unit))}</span></span>
      <span class="tchip t-${esc(m.tier)}" title="Evidence tier ${esc(m.tier)}">${esc(m.tier)}</span>
    </div>`).join("")
    : `<p style="color:var(--muted);margin:0">No headline measurements available for this site.</p>`;

  const gates = (s.gates || []).map((g) => {
    const cls = g.outcome === "PASS" ? "b-pass" : g.outcome === "FAIL" ? "b-fail" : "b-cond";
    return `<div class="gaterow">
      <span class="badge ${cls}" style="flex:none;margin-top:2px">${esc(g.outcome)}</span>
      <span><span class="gt">${esc(g.name)}</span><span class="gr">${esc(g.reason)}</span></span>
    </div>`;
  }).join("");

  document.getElementById("detail").innerHTML = `
    <div class="dhead">
      <h3>${esc(s.name)}</h3>
      <div class="where">${esc(place)}${s.market ? " · " + esc(s.market) : ""} ·
        ${s.lat.toFixed(4)}, ${s.lon.toFixed(4)} · <code>${esc(s.run_id)}</code></div>
    </div>
    <div class="verdicts">${verdictCards}</div>
    <div class="dsec"><h4>Domain scores — ${esc(DATA.meta.profiles.hyperscale_training?.label || "")}</h4>
      <div class="dbars">${doms || "<p style='color:var(--muted);margin:0'>No domains scored.</p>"}</div></div>
    <div class="dsec"><h4>Key measurements</h4>${measured}</div>
    <div class="dsec"><h4>Gates — the knockout checks</h4>${gates || "<p style='color:var(--muted);margin:0'>No gates evaluated.</p>"}</div>
  `;
}

/* ---------- wet-bulb chart ---------- */
function renderChart() {
  const rows = DATA.sites.map((s) => {
    const wb = s.measurements.find((m) => m.factor_id === "wtr.wetbulb_profile" && m.value !== null);
    const fc = s.measurements.find((m) => m.factor_id === "clm.dry_bulb_profile" && m.value !== null);
    return wb ? { name: s.name.split(",")[0], wb: wb.value, fc: fc ? fc.value : null } : null;
  }).filter(Boolean).sort((a, b) => a.wb - b.wb);

  if (!rows.length) { document.getElementById("chart").innerHTML = "<p>No climate data.</p>"; return; }

  const max = Math.max(...rows.map((r) => r.wb), 1);
  const rowH = 40, padT = 34, padL = 150, padR = 78, w = 900;
  const h = padT + rows.length * rowH + 16;

  const bars = rows.map((r, i) => {
    const y = padT + i * rowH;
    const bw = Math.max(2, (r.wb / max) * (w - padL - padR));
    const good = r.wb < 400;
    return `
      <text x="${padL - 12}" y="${y + 15}" text-anchor="end" class="crow"
        style="font-size:13px;fill:var(--ink-2)">${esc(r.name)}</text>
      <rect x="${padL}" y="${y + 3}" width="${bw}" height="17" rx="2"
        fill="${good ? "var(--pass)" : "var(--cond)"}" opacity="${good ? 0.95 : 0.85}"></rect>
      <text x="${padL + bw + 8}" y="${y + 16}" class="crow"
        style="font-size:12.5px;fill:var(--ink-2);font-weight:600">${r.wb.toLocaleString()}</text>
      <text x="${padL}" y="${y + 33}" class="crow"
        style="font-size:10.5px;fill:var(--faint)">${r.fc ? r.fc.toLocaleString() + " free-cooling h/yr" : ""}</text>`;
  }).join("");

  document.getElementById("chart").innerHTML = `
    <div class="crow" style="font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;
      color:var(--faint);margin-bottom:6px">
      Hours per year above 24 °C wet-bulb — lower is better · all Tier A, from ERA5 reanalysis</div>
    <svg viewBox="0 0 ${w} ${h}" role="img"
      aria-label="Wet-bulb hours by site, ascending from Ulanqab at zero to Navi Mumbai at 4320">
      <line x1="${padL}" y1="${padT - 6}" x2="${padL}" y2="${h - 10}"
        stroke="var(--rule)" stroke-width="1"></line>
      ${bars}
    </svg>`;
}

/* ---------- tier ladder ---------- */
function renderLadder() {
  const tc = DATA.meta.tier_counts;
  const total = Object.values(tc).reduce((a, b) => a + b, 0) || 1;
  document.getElementById("ladder").innerHTML = TIER_ORDER.map((t) => {
    const n = tc[t] || 0;
    if (!n) return "";
    const pct = (n / total) * 100;
    const label = pct > 7 ? `${t === "unknown" ? "UNKNOWN" : "TIER " + t} ${n}` : (pct > 3 ? t : "");
    return `<span style="width:${pct}%;background:var(--t${t === "unknown" ? "U" : t});
      ${t === "unknown" ? "color:var(--ink-2)" : ""}" title="${t}: ${n} measurements">${label}</span>`;
  }).join("");
}

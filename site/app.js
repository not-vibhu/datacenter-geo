import {
  REGIONS,
  LAYERS,
  DEFAULT_LAYERS,
  esc,
  located,
  filterFacilities,
  parseCoordinates,
  readView,
  viewHash,
  boundaryFeatures,
  loadSaved,
  within,
  normalizeAtlas,
} from "./lib/core.js";
import { hydrateIcons, icon } from "./lib/icons.js";
import { AtlasMap } from "./lib/map.js";
import * as views from "./lib/views.js";

const $ = (id) => document.getElementById(id);
let atlas,
  data,
  saved = [],
  draft = null,
  editing = false,
  toastTimer;
const boundaryLayers = new Map();
const state = {
  region: "bhopal",
  tab: "explore",
  query: "",
  status: "all",
  limit: 60,
  selected: null,
  basemap: "light",
  heat: "none",
  opacity: 0.55,
  layers: { ...DEFAULT_LAYERS },
};
let storageHealthy = true,
  writingHash = false,
  initialized = false;

function toast(message, action) {
  clearTimeout(toastTimer);
  $("toast").hidden = false;
  $("toast").innerHTML =
    esc(message) +
    (action ? `<button id="toast-action">${esc(action.label)}</button>` : "");
  if (action)
    $("toast-action").onclick = () => {
      action.run();
      $("toast").hidden = true;
    };
  toastTimer = setTimeout(
    () => ($("toast").hidden = true),
    action ? 12000 : 6000,
  );
}
function selectedBoundary() {
  return draft || saved.find((f) => f.id === state.selected?.id);
}
function selectedLayer() {
  return boundaryLayers.get(selectedBoundary()?.id);
}
function currentFacilities() {
  return filterFacilities(data.facilities, {
    ...state,
    region: state.query.trim() ? "india" : state.region,
  });
}
function writeView() {
  if (!atlas || writingHash || !initialized) return;
  history.replaceState(
    null,
    "",
    viewHash(state, atlas.map.getCenter(), atlas.map.getZoom()),
  );
}
function showInspector() {
  $("inspector").classList.add("open");
  if (innerWidth <= 660) $("sidebar").classList.remove("open");
}
function renderSidebar() {
  const facilities = currentFacilities();
  $("sidebar-content").innerHTML =
    state.tab === "layers"
      ? views.layersView(state, data)
      : state.tab === "saved"
        ? views.savedView(saved)
        : views.exploreView(state, data, facilities);
  document.querySelectorAll("[data-tab]").forEach((el) => {
    const selected = el.dataset.tab === state.tab;
    el.setAttribute("aria-selected", selected);
    el.tabIndex = selected ? 0 : -1;
  });
  $("sidebar-content").setAttribute("aria-labelledby", `tab-${state.tab}`);
  $("layer-count").textContent = Object.values(state.layers).filter(
    Boolean,
  ).length;
  $("saved-count").textContent = saved.length;
  atlas.setFacilities(
    facilities,
    state.selected?.type === "facility" ? state.selected.id : null,
  );
}
function renderDetail() {
  const selected = state.selected;
  if (selected?.type === "facility") {
    const f = data.facilities.find((f) => f.id === selected.id);
    $("detail").innerHTML = f
      ? views.facilityView(f)
      : views.overviewView(state, data, saved);
  } else if (selected?.type === "boundary") {
    const f = selectedBoundary();
    $("detail").innerHTML = f
      ? views.boundaryView(f, editing, Boolean(draft))
      : views.overviewView(state, data, saved);
  } else if (selected?.type === "overlay")
    $("detail").innerHTML = views.overlayView(selected.feature);
  else if (selected?.type === "point")
    $("detail").innerHTML = views.pointView(selected.latlng, data);
  else if (selected?.type === "sources")
    $("detail").innerHTML = views.sourcesView(data);
  else $("detail").innerHTML = views.overviewView(state, data, saved);
}
function renderLegend() {
  if (state.heat !== "none") {
    const power = state.heat === "power";
    $("legend").innerHTML =
      `<div class="legend-title">${icon(power ? "bolt" : "layers")}${power ? "Power proximity" : "Facility density"}</div><div class="gradient"></div><div class="legend-range"><span>${power ? "10+ km" : "LOWER"}</span><span>${power ? "0 km" : "HIGHER"}</span></div><p class="legend-note">${power ? "Bhopal · 2 km sample grid · Tier D" : "India · equal-weight facility records"}<br>${power ? "Proximity is not spare capacity." : "Concentration is not investment suitability."}</p>`;
  } else {
    $("legend").innerHTML = `<div class="legend-title">Map layers</div>${
      Object.entries(LAYERS)
        .filter(([id]) => state.layers[id] && id !== "extent")
        .map(
          ([, l]) =>
            `<div class="legend-item"><i class="legend-dot" style="background:${l.color}"></i>${l.name}</div>`,
        )
        .join("") || '<p class="legend-note">All overlays hidden.</p>'
    }`;
  }
}
function renderRegion() {
  const r = REGIONS[state.region];
  $("region-title").textContent = r.name;
  $("region-subtitle").textContent = r.subtitle;
  $("view-label").textContent =
    `${r.name.toUpperCase()} · ${state.region === "bhopal" ? "LOCAL EXPLORATION" : state.region === "mp" ? "REGIONAL VIEW" : "NATIONAL VIEW"}`;
  document.querySelectorAll(".scope-nav [data-region]").forEach((el) => {
    el.classList.toggle("active", el.dataset.region === state.region);
    el.setAttribute(
      "aria-current",
      el.dataset.region === state.region ? "location" : "false",
    );
  });
}
function leaveSelection() {
  if (draft) {
    toast("Save or discard the new boundary before changing selection.");
    showInspector();
    return false;
  }
  if (editing) finishEditing();
  captureBoundaryForm();
  return true;
}
function selectFacility(id, focus = true) {
  if (!leaveSelection()) return;
  const f = data.facilities.find((f) => f.id === id);
  if (!f) return;
  state.selected = { type: "facility", id };
  if (focus && located(f)) atlas.focus(f);
  renderSidebar();
  renderDetail();
  showInspector();
  writeView();
}
function selectRegion(region) {
  if (!Object.hasOwn(REGIONS, region) || !leaveSelection()) return;
  state.region = region;
  state.query = "";
  state.status = "all";
  state.selected = null;
  state.limit = 60;
  $("search").value = "";
  if (region === "india") setHeat("density", false);
  else if (state.heat === "density") setHeat("none", false);
  atlas.region(region);
  renderRegion();
  renderSidebar();
  renderDetail();
  writeView();
}
function setHeat(mode, render = true) {
  state.heat = mode;
  atlas.setHeat(mode, state.opacity);
  renderLegend();
  if (mode === "power" && !data.proximity.cells.length)
    toast(
      "The Bhopal power snapshot is unavailable. Other map tools still work.",
    );
  else if (
    mode === "power" &&
    !within(
      atlas.map.getCenter().lat,
      atlas.map.getCenter().lng,
      REGIONS.bhopal.bbox,
    )
  )
    toast(
      "Power proximity covers the Bhopal pilot. Select Bhopal to inspect it.",
    );
  if (render) renderSidebar();
  writeView();
}
function setBasemap(name) {
  state.basemap = name;
  atlas.setBasemap(name);
  document
    .querySelectorAll("[data-basemap]")
    .forEach((el) =>
      el.setAttribute("aria-pressed", el.dataset.basemap === name),
    );
  writeView();
}
function startDrawing(
  shape = "Polygon",
  facilityId = state.selected?.type === "facility" ? state.selected.id : null,
) {
  if (!leaveSelection()) return;
  state.boundaryFacility = facilityId;
  if (atlas.map.getZoom() < 14)
    toast("Zoom closer before tracing the facility footprint.");
  atlas.draw(shape);
  $("inspector").classList.remove("open");
  $("sidebar").classList.remove("open");
}
function persist(next) {
  if (!storageHealthy) {
    toast(
      "Browser storage is unavailable. Export your boundaries to keep them.",
    );
    return false;
  }
  try {
    localStorage.setItem(
      "dcgeo.boundaries.v1",
      JSON.stringify({ version: 1, features: next }),
    );
    return true;
  } catch {
    storageHealthy = false;
    toast(
      "Could not save to browser storage. Your boundary is still here; export it now.",
    );
    return false;
  }
}
function captureBoundaryForm() {
  const feature = selectedBoundary();
  if (feature && $("boundary-name")) {
    feature.properties.name =
      $("boundary-name").value.trim().slice(0, 120) || "Untitled site";
    feature.properties.kind = $("boundary-kind").value;
    feature.properties.notes = $("boundary-notes").value.slice(0, 2000);
  }
}
function geometryFromLayer(feature, layer) {
  const raw = layer.toGeoJSON(false); // false retains full coordinate precision
  boundaryFeatures(raw, turf);
  feature.geometry = raw.geometry;
  feature.properties.updated = new Date().toISOString();
}
function attachBoundary(feature) {
  const layer = atlas.addBoundary(feature, () => selectBoundary(feature.id));
  boundaryLayers.set(feature.id, layer);
  layer.bindTooltip(esc(feature.properties.name), { className: "draft-label" });
  watchEdits(feature, layer);
  return layer;
}
function watchEdits(feature, layer) {
  layer.on("pm:edit", () => {
    try {
      geometryFromLayer(feature, layer);
      if (!draft) persist(saved);
      if (state.selected?.id === feature.id) {
        const metrics = $("detail").querySelectorAll(".metric strong");
        const ha = turf.area(feature) / 10000;
        if (metrics.length === 2) {
          metrics[0].textContent = views.fmt(ha);
          metrics[1].textContent = views.fmt(ha * 2.47105381);
        }
      }
    } catch (error) {
      toast(`Boundary edit not saved: ${error.message}`);
    }
  });
}
function selectBoundary(id) {
  if (!leaveSelection()) return;
  state.selected = { type: "boundary", id };
  state.tab = "saved";
  const layer = boundaryLayers.get(id);
  if (layer) atlas.focusBoundary(layer);
  renderSidebar();
  renderDetail();
  showInspector();
  writeView();
}
function finishEditing() {
  const feature = selectedBoundary(),
    layer = selectedLayer();
  if (!feature || !layer) return;
  geometryFromLayer(feature, layer);
  layer.pm.disable();
  editing = false;
  if (!draft) persist(saved);
}
function exportJSON(features, name = "boundaries.geojson") {
  const blob = new Blob(
    [JSON.stringify({ type: "FeatureCollection", features }, null, 2)],
    { type: "application/geo+json" },
  );
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function exportCurrent() {
  captureBoundaryForm();
  const feature = selectedBoundary(),
    layer = selectedLayer();
  if (!feature || !layer) return;
  geometryFromLayer(feature, layer);
  exportJSON([feature], "boundary.geojson");
}
function deleteBoundary() {
  const feature = selectedBoundary(),
    layer = selectedLayer();
  if (!feature) return;
  if (editing) {
    layer.pm.disable();
    editing = false;
  }
  const wasSaved = !draft;
  saved = saved.filter((f) => f.id !== feature.id);
  draft = null;
  atlas.parcels.removeLayer(layer);
  boundaryLayers.delete(feature.id);
  persist(saved);
  state.selected = null;
  renderSidebar();
  renderDetail();
  toast("Boundary removed.", {
    label: "Undo",
    run: () => {
      if (wasSaved) {
        saved.push(feature);
        persist(saved);
      } else draft = feature;
      attachBoundary(feature);
      state.selected = { type: "boundary", id: feature.id };
      renderSidebar();
      renderDetail();
      showInspector();
    },
  });
}
async function importFile(file) {
  if (!file) return;
  if (!leaveSelection()) return;
  if (file.size > 2 * 1024 * 1024)
    throw new Error("GeoJSON imports are limited to 2 MB.");
  const features = boundaryFeatures(JSON.parse(await file.text()), turf);
  if (saved.length + features.length > 100)
    throw new Error(
      "This browser workspace supports up to 100 saved boundaries.",
    );
  const now = new Date().toISOString();
  const imported = features.map((f) => ({
    ...f,
    id: crypto.randomUUID(),
    properties: {
      ...f.properties,
      created: now,
      updated: now,
      boundary_status: "user_drawn_unverified",
    },
  }));
  saved.push(...imported);
  imported.forEach(attachBoundary);
  const stored = persist(saved);
  selectBoundary(imported[0].id);
  toast(
    stored
      ? `${imported.length} ${imported.length === 1 ? "boundary" : "boundaries"} imported and saved.`
      : "Imported in memory. Export to keep your work; browser storage is unavailable.",
  );
}
function showPoint(latlng) {
  if (!leaveSelection()) return;
  state.selected = { type: "point", latlng };
  renderDetail();
  showInspector();
  writeView();
}
function goCoordinates() {
  const ll = parseCoordinates($("search").value);
  if (!ll) {
    if (/^[\d+.,\s-]+$/.test($("search").value))
      toast("Enter valid latitude, longitude in WGS84 degrees.");
    return;
  }
  if (!leaveSelection()) return;
  atlas.map.setView(ll, 16);
  showPoint({ lat: ll[0], lng: ll[1] });
}
const actions = {
  overview: () => {
    if (!leaveSelection()) return;
    state.selected = null;
    renderDetail();
    renderSidebar();
    $("inspector").classList.remove("open");
    writeView();
  },
  sources: () => {
    if (!leaveSelection()) return;
    state.selected = { type: "sources" };
    renderDetail();
    showInspector();
  },
  draw: () => startDrawing(),
  import: () => $("boundary-file").click(),
  "clear-search": () => {
    state.query = "";
    state.status = "all";
    $("search").value = "";
    renderSidebar();
  },
  "fit-results": () => {
    const points = currentFacilities()
      .filter(located)
      .map((f) => [f.lat, f.lon]);
    if (points.length)
      atlas.map.fitBounds(points, { padding: [60, 60], maxZoom: 16 });
    else toast("No located facilities match the current filters.");
  },
  more: () => {
    state.limit += 60;
    renderSidebar();
  },
  "satellite-site": () => {
    const f = data.facilities.find((f) => f.id === state.selected?.id);
    if (f) atlas.focus(f);
    setBasemap("satellite");
  },
  "satellite-point": () => {
    const ll = state.selected.latlng;
    atlas.map.setView(ll, 17);
    setBasemap("satellite");
  },
  "draw-facility": () => startDrawing("Polygon", state.selected?.id),
  "edit-boundary": () => {
    captureBoundaryForm();
    const layer = selectedLayer();
    if (!layer) return;
    if (editing) {
      finishEditing();
      toast("Vertex edits applied.");
    } else {
      layer.pm.enable({
        allowSelfIntersection: false,
        snappable: true,
        snapDistance: 12,
      });
      editing = true;
      toast("Drag vertices to edit. Use midpoint handles to add vertices.");
    }
    renderDetail();
  },
  "export-boundary": exportCurrent,
  "export-all": () => exportJSON(saved),
  "delete-boundary": deleteBoundary,
};

function wireUI() {
  document.querySelector(".skip").onclick = (e) => {
    e.preventDefault();
    $("sidebar").classList.add("open");
    $("inspector").classList.remove("open");
    $("search").focus();
  };
  document.addEventListener("click", (e) => {
    const action = e.target.closest("[data-action]");
    const region = e.target.closest("[data-region]");
    const facility = e.target.closest("[data-facility]");
    const boundary = e.target.closest("[data-boundary]");
    const tab = e.target.closest("[data-tab]");
    const base = e.target.closest("[data-basemap]");
    try {
      if (action) actions[action.dataset.action]?.();
      else if (region) selectRegion(region.dataset.region);
      else if (facility) selectFacility(facility.dataset.facility);
      else if (boundary) selectBoundary(boundary.dataset.boundary);
      else if (tab) {
        state.tab = tab.dataset.tab;
        renderSidebar();
      } else if (base) setBasemap(base.dataset.basemap);
    } catch (error) {
      toast(error.message);
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target.dataset.layer) {
      state.layers[e.target.dataset.layer] = e.target.checked;
      atlas.toggle(e.target.dataset.layer, e.target.checked);
      renderSidebar();
      renderLegend();
      writeView();
    }
    if (e.target.dataset.heat) setHeat(e.target.dataset.heat);
    if (e.target.id === "status-filter") {
      state.status = e.target.value;
      state.limit = 60;
      renderSidebar();
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.id === "heat-opacity") {
      state.opacity = Number(e.target.value) / 100;
      atlas.setHeat(state.heat, state.opacity);
      $("opacity-value").textContent = `${e.target.value}%`;
      writeView();
    }
    if (e.target.closest("#boundary-form")) {
      captureBoundaryForm();
      if (!draft) persist(saved);
    }
  });
  document.addEventListener("submit", (e) => {
    if (e.target.id !== "boundary-form") return;
    e.preventDefault();
    try {
      captureBoundaryForm();
      const feature = selectedBoundary(),
        layer = selectedLayer();
      geometryFromLayer(feature, layer);
      if (editing) finishEditing();
      if (draft) {
        if (saved.length >= 100)
          throw new Error("Export boundaries before adding more than 100.");
        saved.push(draft);
        draft = null;
      }
      const stored = persist(saved);
      layer.setTooltipContent?.(esc(feature.properties.name));
      state.tab = "saved";
      renderSidebar();
      renderDetail();
      if (stored)
        toast(
          "Boundary saved on this browser. Export a GeoJSON backup when ready.",
        );
    } catch (error) {
      toast(error.message);
    }
  });
  $("search").addEventListener("input", (e) => {
    state.query = e.target.value;
    state.limit = 60;
    state.tab = "explore";
    renderSidebar();
  });
  $("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    goCoordinates();
  });
  $("boundary-file").onchange = async (e) => {
    try {
      await importFile(e.target.files[0]);
    } catch (error) {
      toast(`Import failed: ${error.message}`);
    } finally {
      e.target.value = "";
    }
  };
  $("share").onclick = async () => {
    writeView();
    try {
      await navigator.clipboard.writeText(location.href);
      toast(
        "View link copied. Locally saved boundaries are not included; export them separately.",
      );
    } catch {
      toast("Copy the address bar to share this map view.");
    }
  };
  $("sources-btn").onclick = actions.sources;
  $("fit-region").onclick = () => atlas.region(state.region);
  $("draw-polygon").onclick = () => startDrawing();
  $("draw-rectangle").onclick = () => startDrawing("Rectangle");
  $("pan-tool").onclick = () => atlas.cancelDraw();
  $("cancel-draw").onclick = () => atlas.cancelDraw();
  $("zoom-in").onclick = () => atlas.map.zoomIn();
  $("zoom-out").onclick = () => atlas.map.zoomOut();
  $("import-boundary").onclick = actions.import;
  $("mobile-explore").onclick = () => {
    $("sidebar").classList.toggle("open");
    $("inspector").classList.remove("open");
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      atlas.cancelDraw();
      return;
    }
    if (e.target.closest("input,textarea,select,[contenteditable=true]"))
      return;
    if (e.key === "/") {
      e.preventDefault();
      $("sidebar").classList.add("open");
      $("search").focus();
    }
    if (e.key.toLowerCase() === "d") startDrawing();
    if (
      e.target.matches("[data-tab]") &&
      ["ArrowLeft", "ArrowRight"].includes(e.key)
    ) {
      e.preventDefault();
      const tabs = ["explore", "layers", "saved"],
        next = (tabs.indexOf(state.tab) + (e.key === "ArrowRight" ? 1 : 2)) % 3;
      state.tab = tabs[next];
      renderSidebar();
      $(`tab-${state.tab}`).focus();
    }
  });
  window.addEventListener("hashchange", () => {
    if (!leaveSelection()) return;
    const view = readView(location.hash, data.facilities);
    writingHash = true;
    state.layers = view.layers;
    state.opacity = view.opacity;
    Object.entries(state.layers).forEach(([key, enabled]) =>
      atlas.toggle(key, enabled),
    );
    state.region = view.region;
    state.selected = view.selected
      ? { type: "facility", id: view.selected }
      : null;
    setBasemap(view.basemap);
    setHeat(view.heat);
    atlas.map.setView(view.center, view.zoom);
    renderRegion();
    renderSidebar();
    renderDetail();
    writingHash = false;
  });
  window.addEventListener("beforeunload", (e) => {
    if (draft || (!storageHealthy && saved.length)) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}

async function boot() {
  hydrateIcons();
  let loadError;
  try {
    const response = await fetch("data/atlas.json", {
      signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`Snapshot HTTP ${response.status}`);
    const normalized = normalizeAtlas(await response.json());
    data = normalized.data;
    loadError = normalized.issues.join(". ");
  } catch (error) {
    data = normalizeAtlas(null).data;
    loadError = error.message;
  }
  const initial = readView(location.hash, data.facilities);
  Object.assign(state, {
    layers: initial.layers,
    opacity: initial.opacity,
    region: initial.region,
    basemap: initial.basemap,
    heat: initial.heat,
    selected: initial.selected
      ? { type: "facility", id: initial.selected }
      : null,
  });
  try {
    saved = loadSaved(localStorage, turf);
  } catch {
    storageHealthy = false;
    loadError =
      "Saved boundary storage could not be read. The original data has been retained.";
  }
  atlas = new AtlasMap(
    data,
    { ...initial, layers: state.layers },
    {
      facility: (id) => selectFacility(id),
      overlay: (feature) => {
        if (!leaveSelection()) return;
        state.selected = { type: "overlay", feature };
        renderDetail();
        showInspector();
        writeView();
      },
      point: (ll) => showPoint(ll),
      tileError: () =>
        toast(
          "Some basemap tiles are unavailable. Try a different basemap; overlays and boundaries still work.",
        ),
      coordinates: (ll) =>
        ($("map-coords").textContent =
          `${Math.abs(ll.lat).toFixed(4)}° ${ll.lat >= 0 ? "N" : "S"} · ${Math.abs(ll.lng).toFixed(4)}° ${ll.lng >= 0 ? "E" : "W"}`),
      move: (center, zoom) => {
        $("zoom-level").textContent = `Zoom ${zoom}`;
        if (!initialized) return;
        const region =
          zoom <= 6
            ? "india"
            : within(center.lat, center.lng, REGIONS.bhopal.bbox) && zoom >= 10
              ? "bhopal"
              : within(center.lat, center.lng, REGIONS.mp.bbox)
                ? "mp"
                : "india";
        if (region !== state.region && !draft) {
          state.region = region;
          renderRegion();
          renderSidebar();
          if (!state.selected) renderDetail();
          if (zoom <= 6 && state.heat === "none") setHeat("density", false);
        }
        writeView();
      },
      created: (layer) => {
        try {
          const raw = boundaryFeatures(layer.toGeoJSON(false), turf)[0];
          const facility = data.facilities.find(
            (f) => f.id === state.boundaryFacility,
          );
          draft = {
            ...raw,
            id: crypto.randomUUID(),
            properties: {
              name: facility
                ? `${facility.name} boundary`
                : `${REGIONS[state.region].name} candidate ${saved.length + 1}`,
              kind: facility ? "existing" : "candidate",
              facility_id: facility?.id || null,
              notes: "",
              created: new Date().toISOString(),
              boundary_status: "user_drawn_unverified",
            },
          };
          const boundaryId = draft.id;
          layer.on("click", () => selectBoundary(boundaryId));
          watchEdits(draft, layer);
          boundaryLayers.set(draft.id, layer);
          state.selected = { type: "boundary", id: draft.id };
          layer.bindTooltip(esc(draft.properties.name));
          renderDetail();
          showInspector();
        } catch (error) {
          atlas.parcels.removeLayer(layer);
          toast(`Boundary rejected: ${error.message}`);
        }
      },
      drawing: (on, shape) => {
        $("draw-hint").hidden = !on;
        $("pan-tool").classList.toggle("active", !on);
        $("pan-tool").setAttribute("aria-pressed", !on);
        [
          ["draw-polygon", "Polygon"],
          ["draw-rectangle", "Rectangle"],
        ].forEach(([id, kind]) => {
          $(id).classList.toggle("active", on && shape === kind);
          $(id).setAttribute("aria-pressed", on && shape === kind);
        });
      },
    },
  );
  saved.forEach(attachBoundary);
  $("zoom-level").textContent = `Zoom ${initial.zoom}`;
  $("map-coords").textContent =
    `${initial.center[0].toFixed(4)}, ${initial.center[1].toFixed(4)}`;
  $("data-date").textContent = data.meta.retrieved
    ? `Snapshot · ${data.meta.retrieved.slice(0, 10)}`
    : "Snapshot unavailable";
  renderRegion();
  renderSidebar();
  renderDetail();
  renderLegend();
  wireUI();
  initialized = true;
  document
    .querySelectorAll("[data-basemap]")
    .forEach((el) =>
      el.setAttribute("aria-pressed", el.dataset.basemap === state.basemap),
    );
  if (state.selected) showInspector();
  if (loadError) {
    toast(
      `${loadError} You can still explore the basemap and work on boundaries.`,
      { label: "Retry", run: () => location.reload() },
    );
    $("data-date").textContent = "Some data unavailable";
  }
  writeView();
}
boot().catch((error) => {
  $("detail").innerHTML =
    `<div class="empty"><strong>The map could not start.</strong>${esc(error.message)}<p>Reload to retry. Saved boundaries have not been changed.</p><button class="button" onclick="location.reload()">Reload</button></div>`;
  $("inspector").classList.add("open");
});

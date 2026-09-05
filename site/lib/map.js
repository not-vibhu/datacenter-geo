import { REGIONS, LAYERS, located, esc } from "./core.js";
import { icon } from "./icons.js";

/** Leaflet lives here; source filtering and user decisions stay in the controller. */
export class AtlasMap {
  constructor(data, initial, callbacks) {
    this.data = data;
    this.callbacks = callbacks;
    this.map = L.map("map", {
      zoomControl: false,
      minZoom: 3,
      maxZoom: 20,
      preferCanvas: true,
      worldCopyJump: false,
    }).setView(initial.center, initial.zoom);
    this.map.setMaxBounds([
      [-80, -180],
      [85, 180],
    ]);
    L.control
      .scale({ imperial: false, position: "bottomleft" })
      .addTo(this.map);
    this.groups = {};
    this.markers = L.layerGroup().addTo(this.map);
    this.parcels = L.featureGroup().addTo(this.map);
    this.layers = { ...initial.layers };
    this.heatMode = initial.heat;
    this.opacity = initial.opacity ?? 0.55;
    this.selected = null;
    this.features = data.facilities;
    this.setBasemap(initial.basemap);
    this.buildOverlays();
    this.map.on("moveend zoomend", () => {
      this.renderFacilities();
      callbacks.move(this.map.getCenter(), this.map.getZoom());
    });
    this.map.on("mousemove", (e) => callbacks.coordinates(e.latlng));
    this.map.on("click", (e) => {
      if (!this.map.pm.globalDrawModeEnabled()) callbacks.point(e.latlng);
    });
    this.map.pm.setGlobalOptions({
      allowSelfIntersection: false,
      snappable: true,
      snapDistance: 12,
      pathOptions: {
        color: "#20614f",
        fillColor: "#3b956b",
        fillOpacity: 0.16,
        weight: 2,
      },
    });
    this.map.on("pm:create", (e) => {
      this.parcels.addLayer(e.layer);
      this.map.pm.disableDraw();
      callbacks.created(e.layer);
    });
    this.map.on("pm:drawend", () => callbacks.drawing(false));
    this.setHeat(initial.heat);
    this.renderFacilities();
  }
  setBasemap(name) {
    if (this.base) this.map.removeLayer(this.base);
    const configs = {
      light: [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        19,
      ],
      satellite: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        'Imagery &copy; <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri &amp; contributors</a>',
        19,
      ],
      terrain: [
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> · SRTM · <a href="https://opentopomap.org">OpenTopoMap</a>',
        17,
      ],
    };
    const [url, attribution, maxNativeZoom] = configs[name] || configs.light;
    this.base = L.tileLayer(url, {
      attribution,
      maxNativeZoom,
      maxZoom: 20,
    }).addTo(this.map);
    let failed = false;
    this.base.on("tileerror", () => {
      if (!failed) {
        failed = true;
        this.callbacks.tileError();
      }
    });
    document
      .querySelector(".map-stage")
      .classList.toggle("satellite", name === "satellite");
  }
  buildOverlays() {
    const styles = {
      line: { color: "#d99935", weight: 2.2, opacity: 0.85 },
      substation: {
        color: "#b87a27",
        fillColor: "#e3ad50",
        fillOpacity: 0.7,
        weight: 1.5,
      },
      water: {
        color: "#79aeca",
        fillColor: "#98c4db",
        fillOpacity: 0.42,
        weight: 1,
      },
      industrial: {
        color: "#a07ba1",
        fillColor: "#b394b4",
        fillOpacity: 0.22,
        weight: 1.3,
      },
    };
    for (const category of Object.keys(styles)) {
      this.groups[category] = L.geoJSON(
        this.data.overlays.features.filter(
          (f) => f.properties.category === category,
        ),
        {
          pmIgnore: true,
          snapIgnore: true,
          style: styles[category],
          pointToLayer: (f, ll) =>
            L.circleMarker(ll, {
              ...styles[category],
              radius: 4,
              pmIgnore: true,
            }),
          onEachFeature: (f, layer) => {
            layer.bindTooltip(esc(f.properties.name || LAYERS[category].name));
            layer.on("click", (e) => {
              L.DomEvent.stopPropagation(e);
              this.callbacks.overlay(f);
            });
          },
        },
      );
    }
    const [s, w, n, e] = this.data.overlays.study_bbox;
    this.groups.extent = L.rectangle(
      [
        [s, w],
        [n, e],
      ],
      {
        color: "#809c77",
        weight: 1.2,
        dashArray: "5 6",
        fill: false,
        interactive: false,
        pmIgnore: true,
      },
    );
    for (const [name, enabled] of Object.entries(this.layers))
      this.toggle(name, enabled);
  }
  toggle(name, enabled) {
    this.layers[name] = enabled;
    if (name === "facilities") {
      this.renderFacilities();
      return;
    }
    const group = this.groups[name];
    if (group) enabled ? group.addTo(this.map) : this.map.removeLayer(group);
  }
  setHeat(mode, opacity = this.opacity) {
    this.heatMode = mode;
    this.opacity = opacity;
    if (this.heat) this.map.removeLayer(this.heat);
    if (mode === "none") return;
    // Uniform point weight: directory count, never MW or investment suitability.
    const points =
      mode === "density"
        ? this.data.facilities
            .filter((f) => located(f) && f.status !== "upcoming")
            .map((f) => [f.lat, f.lon, 0.7])
        : this.data.proximity.cells.map((c) => [c.lat, c.lon, c.intensity]);
    this.heat = L.heatLayer(points, {
      radius: mode === "density" ? 32 : 25,
      blur: 24,
      minOpacity: 0.12,
      maxZoom: mode === "density" ? 7 : 12,
      gradient: {
        0.15: "#6ab98e",
        0.4: "#9fca68",
        0.6: "#e6d26b",
        0.8: "#e49b42",
        1: "#ba5936",
      },
    }).addTo(this.map);
    if (this.heat._canvas) this.heat._canvas.style.opacity = String(opacity);
  }
  setFacilities(features, selected) {
    this.features = features;
    this.selected = selected;
    this.renderFacilities();
  }
  renderFacilities() {
    this.markers.clearLayers();
    if (!this.layers.facilities) return;
    const zoom = this.map.getZoom(),
      groups = new Map();
    const size = zoom < 6 ? 1.2 : zoom < 8 ? 0.35 : zoom < 10 ? 0.055 : 0;
    const bounds = this.map.getBounds().pad(0.2);
    this.features
      .filter((f) => located(f) && bounds.contains([f.lat, f.lon]))
      .forEach((f) => {
        const key = size
          ? `${Math.floor(f.lat / size)},${Math.floor(f.lon / size)}`
          : f.id;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(f);
      });
    groups.forEach((items) => {
      const lat = items.reduce((sum, f) => sum + f.lat, 0) / items.length;
      const lon = items.reduce((sum, f) => sum + f.lon, 0) / items.length;
      if (items.length > 1) {
        const marker = L.marker([lat, lon], {
          pmIgnore: true,
          keyboard: true,
          title: `${items.length} facilities. Zoom in`,
          icon: L.divIcon({
            className: "cluster-pin",
            html: String(items.length),
            iconSize: [34, 34],
          }),
        }).addTo(this.markers);
        marker.on("click", () =>
          this.map.fitBounds(
            items.map((f) => [f.lat, f.lon]),
            { padding: [50, 50], maxZoom: zoom + 3 },
          ),
        );
      } else {
        const f = items[0];
        const marker = L.marker([lat, lon], {
          pmIgnore: true,
          keyboard: true,
          title: f.name,
          alt: f.name,
          icon: L.divIcon({
            className: `facility-pin ${f.kind} ${f.id === this.selected ? "selected" : ""}`,
            html: icon("server"),
            iconSize: [25, 25],
          }),
        }).addTo(this.markers);
        marker.bindTooltip(esc(f.name), { direction: "top", offset: [0, -13] });
        marker.on("click", () => this.callbacks.facility(f.id));
      }
    });
  }
  region(name) {
    const r = REGIONS[name];
    this.map.setView(r.center, r.zoom, {
      animate: !matchMedia("(prefers-reduced-motion: reduce)").matches,
    });
  }
  focus(f) {
    if (located(f)) this.map.setView([f.lat, f.lon], 16, { animate: false });
  }
  draw(shape = "Polygon") {
    this.map.pm.disableDraw();
    this.map.pm.enableDraw(shape, { allowSelfIntersection: false });
    this.callbacks.drawing(true, shape);
  }
  cancelDraw() {
    this.map.pm.disableDraw();
    this.callbacks.drawing(false);
  }
  addBoundary(feature, onClick) {
    const container = L.geoJSON(feature, {
      style: {
        color: "#2b8060",
        weight: 2,
        fillColor: "#4fa175",
        fillOpacity: 0.15,
      },
    });
    const layer = container.getLayers()[0];
    this.parcels.addLayer(layer);
    layer.on("click", onClick);
    return layer;
  }
  focusBoundary(layer) {
    this.map.fitBounds(layer.getBounds(), { padding: [55, 55], maxZoom: 18 });
  }
}

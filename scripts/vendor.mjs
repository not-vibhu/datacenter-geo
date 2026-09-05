// Pinned, local browser assets. Only basemap tiles require a third-party runtime request.
import { mkdir, copyFile, cp } from "node:fs/promises";

const files = {
  "leaflet/dist/leaflet.js": "leaflet.js",
  "leaflet/dist/leaflet.css": "leaflet.css",
  "leaflet/LICENSE": "leaflet-LICENSE",
  "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.js": "geoman.js",
  "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css": "geoman.css",
  "@geoman-io/leaflet-geoman-free/LICENSE": "geoman-LICENSE",
  "@turf/turf/turf.min.js": "turf.js",
  "@turf/turf/LICENSE": "turf-LICENSE",
  "leaflet.heat/dist/leaflet-heat.js": "heat.js",
  "leaflet.heat/LICENSE": "heat-LICENSE",
};
await mkdir("site/vendor", { recursive: true });
for (const [source, target] of Object.entries(files)) {
  await copyFile(`node_modules/${source}`, `site/vendor/${target}`);
}
await cp("node_modules/leaflet/dist/images", "site/vendor/images", {
  recursive: true,
});
console.log("Copied pinned map libraries and their licenses to site/vendor.");

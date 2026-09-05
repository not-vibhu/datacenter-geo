import test from "node:test";
import assert from "node:assert/strict";
import * as turf from "@turf/turf";
import { readFileSync } from "node:fs";
import {
  filterFacilities,
  located,
  parseCoordinates,
  boundaryFeatures,
  loadSaved,
  readView,
  viewHash,
  bandsOverlap,
  safeURL,
} from "../../site/lib/core.js";

const polygon = {
  type: "Feature",
  geometry: {
    type: "Polygon",
    coordinates: [
      [
        [77.4, 23.2],
        [77.41, 23.2],
        [77.41, 23.21],
        [77.4, 23.21],
        [77.4, 23.2],
      ],
    ],
  },
  properties: { name: "Bhopal test", notes: "A draft", kind: "candidate" },
};
const data = JSON.parse(
  readFileSync(new URL("../../site/data/atlas.json", import.meta.url)),
);

test("Bhopal inventory includes an unlocated announcement, but it cannot be mapped", () => {
  const found = filterFacilities(data.facilities, { region: "bhopal" });
  assert.ok(found.some((f) => f.id === "mp-state-dc"));
  assert.ok(found.some((f) => f.id === "pdb-12734"));
  const upcoming = found.find((f) => f.id === "ctrls-bhopal");
  assert.equal(located(upcoming), false);
  assert.equal(upcoming.status, "upcoming");
});
test("national search and status filters do not erase the underlying inventory", () => {
  assert.ok(
    filterFacilities(data.facilities, {
      region: "india",
      query: "indore",
      status: "listed",
    }).length >= 2,
  );
  assert.equal(
    filterFacilities(data.facilities, { region: "bhopal", status: "upcoming" })
      .length,
    1,
  );
  assert.equal(
    filterFacilities(data.facilities, {
      region: "india",
      query: "nonexistent-xyz",
    }).length,
    0,
  );
});
test("coordinates accept latitude, longitude and reject invalid or non-finite input", () => {
  assert.deepEqual(parseCoordinates("23.2599, 77.4126"), [23.2599, 77.4126]);
  for (const bad of [
    "91,77",
    "23,181",
    "NaN,77",
    "",
    "23,77,11",
    "23., 77",
    "Bhopal",
  ])
    assert.equal(parseCoordinates(bad), null);
});
test("boundary import/export preserves exact vertices, holes and named metadata", () => {
  const withHole = structuredClone(polygon);
  withHole.geometry.coordinates.push([
    [77.402, 23.202],
    [77.402, 23.204],
    [77.404, 23.204],
    [77.404, 23.202],
    [77.402, 23.202],
  ]);
  const [parsed] = boundaryFeatures(
    { type: "FeatureCollection", features: [withHole] },
    turf,
  );
  assert.deepEqual(parsed.geometry, withHole.geometry);
  assert.equal(parsed.properties.name, "Bhopal test");
  assert.ok(turf.area(parsed) < turf.area(polygon));
});
test("invalid rings, self intersections, non-polygons and invalid coordinate ranges are rejected", () => {
  const bad = [
    { type: "Point", coordinates: [77, 23] },
    { type: "Polygon", coordinates: [] },
    {
      type: "Polygon",
      coordinates: [
        [
          [77, 23],
          [78, 24],
          [78, 23],
          [77, 24],
          [77, 23],
        ],
      ],
    },
    {
      type: "Polygon",
      coordinates: [
        [
          [177, 23],
          [188, 23],
          [188, 24],
          [177, 23],
        ],
      ],
    },
    {
      type: "Polygon",
      coordinates: [
        [
          [77, 23],
          [78, 23],
          [78, 24],
          [77, 24],
        ],
      ],
    },
  ];
  for (const geometry of bad)
    assert.throws(() => boundaryFeatures(geometry, turf));
});
test("saved local boundary survives serialization with all geometry intact", () => {
  const saved = { version: 1, features: [{ ...polygon, id: "parcel-1" }] };
  const restored = loadSaved({ getItem: () => JSON.stringify(saved) }, turf);
  assert.deepEqual(restored[0].geometry, polygon.geometry);
  assert.equal(restored[0].id, "parcel-1");
  assert.throws(() => loadSaved({ getItem: () => "broken" }, turf));
});
test("share links restore the exact view and reject malicious or malformed state", () => {
  const hash = viewHash(
    {
      region: "mp",
      basemap: "satellite",
      heat: "density",
      selected: { type: "facility", id: "pdb-12734" },
    },
    { lat: 23.12345, lng: 77.54321 },
    17,
  );
  const restored = readView(hash, data.facilities);
  assert.deepEqual(restored.center, [23.12345, 77.54321]);
  assert.equal(restored.zoom, 17);
  assert.equal(restored.selected, "pdb-12734");
  const bad = readView(
    "#region=__proto__&view=NaN,999,80&base=javascript:x&facility=missing",
  );
  assert.equal(bad.region, "bhopal");
  assert.equal(bad.zoom, 12);
  assert.equal(bad.basemap, "light");
  assert.equal(bad.selected, null);
  assert.equal(safeURL("javascript:alert(1)"), null);
});
test("overlapping and touching score ranges never imply a defensible ordering", () => {
  assert.equal(
    bandsOverlap({ score: 80, band: 10 }, { score: 65, band: 10 }),
    true,
  );
  assert.equal(
    bandsOverlap({ score: 80, band: 10 }, { score: 60, band: 10 }),
    true,
  );
  assert.equal(
    bandsOverlap({ score: 80, band: 10 }, { score: 59, band: 10 }),
    false,
  );
});

test("broken infrastructure data leaves the facility inventory intact", async () => {
  const { normalizeAtlas } = await import("../../site/lib/core.js");
  const { data: partial, issues } = normalizeAtlas({
    facilities: data.facilities,
    meta: data.meta,
  });
  assert.equal(partial.facilities.length, data.facilities.length);
  assert.equal(partial.overlays.features.length, 0);
  assert.ok(issues.includes("Infrastructure overlays unavailable"));
  assert.equal(partial.meta.osm_retrieved, undefined);
  assert.equal(normalizeAtlas(null).data.facilities.length, 0);
});

test("share links preserve overlay selections and heatmap opacity", () => {
  const hash = viewHash(
    {
      region: "india",
      basemap: "light",
      heat: "power",
      layers: { facilities: false, water: true, industrial: true },
      opacity: 0.7,
    },
    { lat: 23.2, lng: 77.4 },
    12,
  );
  const restored = readView(hash);
  assert.equal(restored.layers.facilities, false);
  assert.equal(restored.layers.water, true);
  assert.equal(restored.layers.industrial, true);
  assert.equal(restored.layers.line, false);
  assert.equal(restored.opacity, 0.7);
});

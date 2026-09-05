# India infrastructure atlas

The working product starts with a map, not a score. Open Bhopal, inspect an existing
facility or the infrastructure around a location, trace a parcel, and carry that
exact geometry into an evidence-backed investigation. The expansion sequence is
**Bhopal → Madhya Pradesh → India**.

## Run it

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
# Open http://127.0.0.1:8765
```

Browser libraries are pinned and vendored, so serving the app does not require npm,
a build server, API keys or live analysis APIs. Street, terrain and satellite tiles
still come from their attributed providers. Existing reports are at `diligence.html`.

For development and verification:

```bash
npm ci
npm test
npm run vendor                       # reproduce committed browser assets
uv run pytest -q
uv run ruff check .
uv run python scripts/build_atlas_data.py   # offline, deterministic
```

## What this version does

- Opens on Bhopal with a national facility directory behind it. Region buttons,
  cluster clicks, search, coordinates and zoom controls support geographic drill-down.
- Provides map, satellite and terrain basemaps. Providers have different native zoom
  limits; overzooming imagery does not add survey accuracy.
- Separates directory listings, government-documented facilities and upcoming
  projects. Unlocated projects appear in the inventory, never as invented map pins.
- Shows attributed Bhopal power lines, substations, water bodies and industrial
  land-use geometry. Clicking an overlay opens its source and source tags.
- Provides two explicitly named heatmaps: national facility density and Bhopal
  substation proximity. Neither is an investment suitability score.
- Draws Polygon and Rectangle boundaries; edits vertices; accepts valid GeoJSON
  Polygon/MultiPolygon imports including holes; rejects crossing rings and invalid
  coordinates; retains full coordinate precision on export.
- Saves up to 100 boundaries in browser local storage with names, notes, timestamps,
  draft status and optional links to facility records. Export is the portable backup.
  Import permits at most 2 MB and 10,000 vertices per feature.
- Shares region, viewport, basemap, selected facility, overlay visibility, heatmap
  and opacity in the URL. Private local boundaries are deliberately not in the URL.
- Keeps the map and boundary tools usable when the atlas snapshot cannot load, and
  labels missing sections. An infrastructure-section failure does not erase the
  facility inventory. Storage failures retain the in-memory boundary and prompt export.

The source snapshots are **not a complete facility census**. PeeringDB listings are
community maintained and may describe exchanges or multiple records at one campus.
They do not establish operating status, utility headroom or available commercial MW.

## Data contract and provenance

| File | Purpose |
|---|---|
| `data/atlas/facilities.json` | Allowlisted PeeringDB India fields; no personal contact details |
| `data/atlas/bhopal-osm.geojson` | Attributed OSM features in the pilot study extent |
| `data/atlas/curated.json` | Individually sourced government and upcoming-project records |
| `site/data/atlas.json` | Deterministic browser payload and derived proximity samples |
| `scripts/build_atlas_data.py` | Conversion, validation, optional refresh and offline build |
| `site/lib/core.js` | Filtering, view URLs, boundary validation and storage contract |
| `site/lib/map.js` | Basemaps, geometry overlays, clusters and drawing controls |
| `site/lib/views.js` | Sidebar and inspector rendering |
| `site/app.js` | UI events, selection, persistence and failure handling |

The Bhopal study extent is `[south=23.08, west=77.18, north=23.48, east=77.65]`.
It is a **chosen research window**, not an administrative boundary. MP and India
bookmarks are navigation extents, not official boundary datasets.

Refresh is explicitly separate from browsing:

```bash
uv run python scripts/build_atlas_data.py --refresh
```

The refresh paginates PeeringDB, requests power and land features separately, tries
bounded Overpass mirror requests, rejects timeout remarks and empty responses, and
only replaces source snapshots once both sources have succeeded. A failed request
leaves the previously committed snapshots usable. Review source changes before
publishing. Normal CI and site builds make no source API calls.

The OSM importer supports nodes and ways. Multipolygon relations need proper
assembly and are excluded rather than guessed. Counts of exclusions are retained.
Mapped water is not a flood-risk layer; mapped industrial land is not evidence of
available land; mapped substations are not evidence of available capacity.

### Heatmap interpretation

**Facility density:** equal-weight points at located facility records. A Leaflet
heat kernel indicates relative concentration. Search filters affect inventory and
pins; the heatmap deliberately describes the entire national snapshot. It is not
normalized by land area, population, capacity or market demand.

**Power proximity:** a 2 km sampling grid within the Bhopal study extent. Distance
is great-circle distance to the area centroid of the nearest mapped substation.
The displayed intensity is `max(0, 1 - distance_km / 10)`. The 10 km fade is a display
parameter, not an engineering constraint. This is Tier D derived context. Boundary
samples may be biased because substations outside the study extent are not included.
Voltage, capacity, topology, connectability and land availability are not modeled.

**Investment suitability:** deliberately not represented by either surface. A
national investment heatmap needs the gated evidence pipeline below. An empty area
means no data for this layer, not poor investment potential.

### Key source references

- [PeeringDB facility API](https://www.peeringdb.com/apidocs/) and
  [data ownership policy](https://docs.peeringdb.com/gov/misc/2020-04-06_PeeringDB_Data_Ownership_Policy_Document_v1.0.pdf).
- [MPSEDC SDWAN tender](https://www.tcil.net.in/tender/pdf/25e1407_1.pdf): printed
  page 38 identifies the State Data Centre in the State IT Centre; printed page 111
  supplies the campus reference coordinate. The published point is not a surveyed footprint.
- [CtrlS operator inventory](https://www.ctrls.com/business-continuity-data-centers-in-india/)
  lists the Bhopal Edge DC as upcoming. No exact coordinate is inferred from the city name.
- [OpenStreetMap contributors / ODbL](https://www.openstreetmap.org/copyright).

## Exact boundary handoff

Export a single boundary from its inspector, then:

```bash
uv run dcgeo analyze --boundary boundary.geojson --profile hyperscale_training
```

`--boundary` and `--at` are mutually exclusive. The CLI validates rings, coordinate
ranges, topology, file size and vertex limits before calling any source. It keeps
the exact Polygon/MultiPolygon, including holes, in both `analysis.json` and
`site.geojson`. It picks an interior reference point for existing point-based
adapters; the stored `centroid` field records that reference point and the site notes
say so. This release does **not** turn point-based adapters into parcel-wide hazard
or land-availability assessments. It does not establish an official facility boundary.

## The path to a national investment product

### 1. Complete Bhopal as a decision workflow

Deliver one defensible parcel investigation from map selection to reviewed evidence.

- Ingest verified MPSEDC / MPIDC industrial parcels and lease terms with survey IDs.
- Obtain MPPTCL and distribution-company substation ratings, planned upgrades,
  sanctioned loads and connection pathways. Presence alone cannot answer this.
- Add terrain, land cover, protected areas and riverine/pluvial flood screening that
  **intersects the polygon**, including coverage and resolution on each result.
- Add a durable analysis-job service: queued, measuring, awaiting research, complete,
  partial and failed states; retry individual adapters and retain partial evidence.
- Store boundary versions and evidence lineage in PostgreSQL/PostGIS. Geometry edits
  must create new versions and invalidate affected measurements.
- Scope gates per workload profile. The current engine's shared gate list can carry
  the first profile's outcome into other profiles; resolve this before presenting
  multiple workload decisions as investment advice.
- Make scenario assumptions override the intended selected measurement explicitly;
  a new Tier D assumption must not silently lose to an older Tier A reading.

Acceptance: a named Bhopal parcel has an exact, versioned boundary; an auditable set
of measured and unknown inputs; a profile-specific decision; and assigned tasks to
resolve every blocking unknown. A dead source produces a partial run, not a failed UI.

### 2. Expand from Bhopal to MP

- Add official district boundaries and a coverage registry per district and source.
- Build independently refreshable infrastructure tiles rather than a larger global JSON.
- Expand parcel and utility data to Indore, Pithampur, Gwalior, Jabalpur and the
  corridors supported by source evidence, without prescribing an investment ranking.
- Use viewport queries and spatial indexes; deduplicate directory records at campus
  level while preserving each source record and conflicting claims.
- Add shared shortlists, boundary history, review roles and evidence attachments.

Acceptance: a user can compare parcels across MP on the same workload and evidence
rules, understand differences in coverage, and collaborate without exporting files.

### 3. Build the India screening surface

- Use a versioned spatial grid (e.g. H3) with coarse-to-fine resolution. Each cell
  carries measurements, gate results, confidence, freshness and model version.
- Run national coarse screening for power infrastructure, slope, land cover,
  protected areas and flood exposure. Do not call a centroid a parcel assessment.
- Keep **suitability**, **coverage/confidence**, **constraints** and **existing
  deployment density** as separate selectable layers.
- Never interpolate a high suitability score across unmeasured cells. Mask cells
  with missing gate-critical evidence and explain the missing input on click.
- Use vector tiles / PMTiles for large layers and an object store for versioned raster
  tiles. Fetch details on selection; do not ship national raw geometry to every browser.
- Allow drill-down from country cells to state/district clusters to actual parcels.
  A candidate is promoted to full diligence only when source coverage supports it.
- Validate against operating facilities and negative controls, including places with
  strong proximity signals but unavailable capacity or blocked permits.

Acceptance: each colored investment-screening cell explains its score and exclusions,
is reproducible at its model version, and identifies what still requires verification.

## API accounts and cost controls

No paid account is required for this pilot. Before public traffic grows, use a
production map/imagery provider or self-hosted tiles instead of depending on free
community infrastructure. The basemap adapter is isolated for this change.

Candidate purchases should close a specific evidence gap: licensed imagery for
boundary review, reliable terrain and hazard tiles, carrier routes, or utility and
parcel data. A generic maps key does not unlock spare utility capacity or land title.

For any future provider: keep secret credentials on the job service, use explicit
quotas and spend caps, and expose provider status without blocking other layers.
Public browser map keys must be origin-restricted. Authenticated boundary data must
stay out of public snapshot builds. User-provided keys are never committed to this repo.

## Verification record

This release has automated tests for boundary geometry and holes, CLI roundtrips,
invalid input rejection before API calls, data provenance, deterministic atlas
builds, missing snapshot sections, filters, URL state and confidence-band overlap.

Browser checks cover Bhopal and national views, satellite imagery, mobile layer
controls, drawing and editing a polygon, saving/reloading, downloading GeoJSON and
validating that download through the CLI boundary parser. A deliberately blocked
atlas request leaves drawing and the basemap usable. Browser QA uses isolated test
sessions; test parcels are not part of the published data.

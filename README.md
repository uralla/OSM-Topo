# OSM-Topo

**OSM-Topo** is an open build project for unofficial Garmin topographic maps based on OpenStreetMap data. The maps are designed primarily for outdoor navigation on Garmin handheld devices, where readability on a small screen is more important than simply displaying every available OSM object at every zoom level.

The current generation of the project is more than an mkgmap style. It is a reproducible cartographic pipeline with semantic preprocessing, adaptive visibility, DEM/contour integration, validation, automated scheduling and atomic publication of Garmin IMG and BaseCamp GMAPI packages.

## What makes these maps different

- **Garmin-oriented cartography.** Styles, POI types, labels, polygons, tunnels and drawing order are tuned for real Garmin behaviour rather than only for successful compilation.
- **Semantic preprocessing.** OSM objects can be enriched before splitter/mkgmap using surrounding context, density and object semantics, allowing the map to reduce clutter on distant zoom levels without simply deleting source data.
- **Topographic data.** Regional builds can include DEM/elevation data and contour lines; marine areas can also use depth data where configured.
- **Adaptive labels and landmarks.** Long labels are handled separately from source names, while important geographic features can remain useful as visual anchors at smaller scales.
- **Reproducible builds.** Product identity, FID/PID, tile ranges, extraction polygons and build parameters are defined in a central manifest and validated before publication.
- **Safe automatic updates.** Builds run under a scheduler, keep publication history, publish atomically and expose public update-status data for the download catalogue.
- **BaseCamp packages.** GMAPI archives include a user-scoped Windows installer/uninstaller and do not require registry editing or administrator rights.

The project remains intentionally pragmatic: Garmin device behaviour is treated as the final rendering test, and optimizations are accepted or rejected based on the resulting map rather than CPU utilization alone.

### Maps and downloads

- Project page and map catalogue: https://www.uralla.ru/ural-garmin-topo-img-map-16505.html
- Published map files: https://www.uralla.ru/garmin.img/

The maps are independent, unofficial user-generated products. Garmin is a trademark of Garmin Ltd. or its subsidiaries. OpenStreetMap data is provided by OpenStreetMap contributors under the applicable OSM data licence.

## Repository layout

- `config/` — build manifests and versioned configuration.
- `catalog/` — curated semantic-preprocessor catalogues.
- `docs/` — architecture notes, audits and historical project context.
- `scripts/` — helper and migration utilities.
- `styles/` — mkgmap style and TYP sources.
- `tests/` — regression tests.
- `uralla_build/` — Python build orchestration and semantic preprocessing.

## External build data

Large or static build inputs are intentionally not versioned. They live below the host-specific `data_root` configured in `host.yaml`:

- `input/` — source OSM PBF, bounds, sea and GeoNames inputs;
- `elevation/` — pre-generated elevation/contour PBF files;
- `poly/` — product extraction polygons.

Manifest paths such as `poly/crimea.poly` are resolved relative to `data_root`, not relative to the repository checkout.

The very large HGT/DEM tree remains separately configurable through `dem_root`.

## POI context diagnostic build

Run `bash scripts/test-poi-context.sh [product]` from the repository root (default product: `crimea`). It performs a normal full product build, keeps the complete console log under `logs/poi-context/`, and writes a compact `*.poi.txt` extract containing the POI context/activity diagnostics used while tuning adaptive visibility.

## Documentation

See `docs/README.md` for the documentation index.

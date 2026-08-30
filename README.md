# OSM-Topo

Manifest-driven build project for Garmin topographic maps based on OpenStreetMap data.

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

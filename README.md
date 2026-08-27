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

## Local build data

Large or static build inputs are intentionally not versioned. The following paths are local working data and are ignored by Git:

- `poly/`
- `input/`
- `elevation/`
- `OSM/`
- `dem-files.tsv`

Paths such as `poly/*.poly` remain stable in `config/maps.yaml`; keep the corresponding local directories beside the repository checkout on the build host.

## Documentation

See `docs/README.md` for the documentation index.

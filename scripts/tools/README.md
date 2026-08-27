# Helper tools

These are standalone maintenance utilities, not normal build-runner entry points.

## `copy-dem-to-osm.sh`

Portable helper for creating a smaller working DEM subset.

Usage:

1. Copy `copy-dem-to-osm.sh` into the source DEM directory.
2. Put `dem-required-files.txt` in the same directory.
3. Run the copied script there.

The script verifies every listed source file, copies the required files into an `OSM/` subdirectory, and verifies the copied sizes. It intentionally resolves paths relative to its own location because it is meant to be copied into the DEM dataset directory before use.

The large source DEM tree and generated `OSM/` subset are local data and are not versioned in this repository.

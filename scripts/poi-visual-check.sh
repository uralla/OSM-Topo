#!/usr/bin/env bash
set -Eeuo pipefail

# Print coordinates for selected Crimea POIs used to visually verify adaptive LOD.
# Also writes a GPX file with the same points.
# Usage:
#   bash scripts/poi-visual-check.sh [crimea-source.osm.pbf]

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs/poi-context"
GPX_OUT="$LOG_DIR/crimea-visual-check.gpx"
mkdir -p "$LOG_DIR"

python_is_usable() {
    local candidate="$1"
    command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]] || return 1
    "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1 || return 1
    "$candidate" -c 'import osmium; raise SystemExit(0 if hasattr(osmium, "FileProcessor") else 1)' >/dev/null 2>&1 || return 1
    return 0
}

PYTHON_BIN=""
for candidate in \
    "$REPO_ROOT/.venv/bin/python" \
    "$REPO_ROOT/venv/bin/python" \
    python3.13 python3.12 python3.11 \
    /usr/bin/python3.13 /usr/bin/python3.12 /usr/bin/python3.11 \
    /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 \
    python3 python
do
    if python_is_usable "$candidate"; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: Python >= 3.11 with PyOsmium FileProcessor is required." >&2
    exit 2
fi

SOURCE="${1:-}"
if [[ -z "$SOURCE" ]]; then
    for candidate in \
        /mnt/g/garmin_dev/input/crimean-fed-district-latest.osm.pbf \
        /mnt/nod/input/crimean-fed-district-latest.osm.pbf
    do
        if [[ -s "$candidate" ]]; then
            SOURCE="$candidate"
            break
        fi
    done
fi

if [[ -z "$SOURCE" || ! -s "$SOURCE" ]]; then
    echo "ERROR: Crimea source PBF not found." >&2
    echo "Usage: bash scripts/poi-visual-check.sh /path/to/crimean-fed-district-latest.osm.pbf" >&2
    exit 2
fi

"$PYTHON_BIN" - "$SOURCE" "$GPX_OUT" <<'PY'
from __future__ import annotations

from html import escape
from pathlib import Path
import sys
import osmium

source = Path(sys.argv[1])
gpx_path = Path(sys.argv[2])

# These are intentionally chosen to compare common+remote POIs against
# ordinary settlement/urban controls in the same production source.
targets = {
    3190064498: ("REMOTE food", "Магазин Маячок", "expected resolution 22"),
    3161488492: ("REMOTE accommodation", "Чайка Батилиман", "expected resolution 22"),
    1293202179: ("REMOTE transit", "Маяк", "expected resolution 22"),
    1293202180: ("REMOTE transit", "Еникале", "expected resolution 22"),
    897654209: ("CONTROL settlement transit", "Старый Крым", "ordinary common control"),
    6452076715: ("CONTROL settlement accommodation", "Старый Крым", "ordinary common control"),
    272507237: ("CONTROL urban food", "Лидер", "ordinary common control"),
}

found = {}
for item in osmium.FileProcessor(str(source)):
    if item.type_str() != "n":
        continue
    oid = int(item.id)
    if oid not in targets:
        continue
    if not item.location.valid():
        continue
    tags = {str(k): str(v) for k, v in item.tags}
    found[oid] = {
        "lat": float(item.location.lat),
        "lon": float(item.location.lon),
        "name": tags.get("name") or targets[oid][1],
        "tags": tags,
    }
    if len(found) == len(targets):
        break

print(f"Source: {source}")
print("\nCrimea adaptive LOD visual check")
print("=" * 78)

for oid, (group, fallback_name, expectation) in targets.items():
    data = found.get(oid)
    if data is None:
        print(f"MISSING  n{oid}  {group}  {fallback_name}")
        continue
    print(
        f"{group:30}  n{oid:<11}  "
        f"{data['lat']:.6f}, {data['lon']:.6f}  "
        f"{data['name']}  [{expectation}]"
    )

missing = [oid for oid in targets if oid not in found]

waypoints = []
for oid, (group, fallback_name, expectation) in targets.items():
    data = found.get(oid)
    if data is None:
        continue
    name = f"{group} - {data['name']}"
    desc = f"OSM node {oid}; {expectation}"
    waypoints.append(
        f'  <wpt lat="{data["lat"]:.7f}" lon="{data["lon"]:.7f}">\n'
        f'    <name>{escape(name)}</name>\n'
        f'    <desc>{escape(desc)}</desc>\n'
        f'  </wpt>'
    )

gpx = "\n".join([
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<gpx version="1.1" creator="OSM-Topo poi-visual-check" xmlns="http://www.topografix.com/GPX/1/1">',
    *waypoints,
    '</gpx>',
    '',
])
gpx_path.write_text(gpx, encoding="utf-8")

print("=" * 78)
print(f"GPX: {gpx_path}")
print("\nTest: open each point on the freshly built Crimea.OSM and zoom out.")
print("REMOTE common POIs should survive to the resolution-22 level; controls should not.")

if missing:
    raise SystemExit(1)
PY

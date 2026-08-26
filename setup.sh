#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

HOST_CONFIG="${URALLA_HOST_CONFIG:-$REPO_ROOT/config/host.yaml}"
DATA_ROOT="${URALLA_DATA_ROOT:-$HOME/garmin_lab}"
WORK_ROOT="${URALLA_WORK_ROOT:-$DATA_ROOT}"
PUBLISH_ROOT="${URALLA_PUBLISH_ROOT:-$DATA_ROOT/output}"
DEM_ROOT="${URALLA_DEM_ROOT:-$DATA_ROOT/dem}"
TOOLS_ROOT="${URALLA_TOOLS_ROOT:-$REPO_ROOT/tools}"
VENV="${URALLA_VENV:-$REPO_ROOT/.venv}"

log() { printf '[setup] %s\n' "$*"; }
die() { printf '[setup] ERROR: %s\n' "$*" >&2; exit 1; }

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "root privileges are required for: $* (sudo is not installed)"
  fi
}

OS="$(uname -s)"
case "$OS" in
  Linux)
    if ! command -v apt-get >/dev/null 2>&1; then
      die "Linux setup currently supports Ubuntu/Debian apt-based hosts"
    fi
    if grep -qi microsoft /proc/version 2>/dev/null; then
      log "platform: WSL Ubuntu/Debian"
    else
      log "platform: Ubuntu/Debian Linux"
    fi
    log "installing base Python/runtime prerequisites"
    as_root apt-get update
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3 python3-venv python3-pip ca-certificates git
    ;;

  Darwin)
    log "platform: macOS"
    command -v brew >/dev/null 2>&1 || die "Homebrew is required; install it from https://brew.sh and rerun setup.sh"
    if ! command -v python3 >/dev/null 2>&1; then
      log "installing Python with Homebrew"
      brew install python
    fi
    ;;

  *)
    die "unsupported platform: $OS"
    ;;
esac

PYTHON="$(command -v python3 || true)"
[[ -n "$PYTHON" ]] || die "python3 is not available after system setup"

PY_MAJOR="$($PYTHON -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$($PYTHON -c 'import sys; print(sys.version_info.minor)')"
if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 11) )); then
  die "Python >= 3.11 is required; found $($PYTHON --version 2>&1)"
fi
log "python: $($PYTHON --version 2>&1)"

if [[ ! -x "$VENV/bin/python" ]]; then
  log "creating virtual environment: $VENV"
  "$PYTHON" -m venv "$VENV"
else
  log "virtual environment already exists: $VENV"
fi

log "installing/updating Python project dependencies"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/python" -m pip install -e "$REPO_ROOT"

if [[ ! -f "$HOST_CONFIG" ]]; then
  log "creating local host config: $HOST_CONFIG"
  mkdir -p "$(dirname "$HOST_CONFIG")" "$DATA_ROOT" "$WORK_ROOT" "$PUBLISH_ROOT" "$PUBLISH_ROOT/mapsource" "$DEM_ROOT" "$TOOLS_ROOT"
  cat > "$HOST_CONFIG" <<EOF
schema_version: 1

paths:
  data_root: $DATA_ROOT
  work_root: $WORK_ROOT
  publish_root: $PUBLISH_ROOT
  tools_root: $TOOLS_ROOT
  dem_root: $DEM_ROOT

publication:
  img_subdir: .
  gmapi_subdir: mapsource
  img_archive: false
  gmapi_zip_mode: store
  split_zip_volumes: false

resources:
  product_concurrency: 1
  minimum_free_gib: 20
EOF
else
  log "using existing host config: $HOST_CONFIG"
fi

# Ensure local writable roots exist. External data files themselves are not created.
mkdir -p "$WORK_ROOT" "$PUBLISH_ROOT" "$PUBLISH_ROOT/mapsource" "$DEM_ROOT" "$TOOLS_ROOT"

log "installing/checking system tools and pinned mkgmap/splitter"
"$VENV/bin/python" -m uralla_build \
  --host "$HOST_CONFIG" \
  bootstrap --repo-root "$REPO_ROOT" --tools-lock "$REPO_ROOT/config/tools.lock.yaml" \
  --apply --capture-checksums

if [[ "$OS" == "Darwin" ]]; then
  # Homebrew's OpenJDK is keg-only on macOS. Register it with macOS so /usr/bin/java
  # and Java-aware applications can locate the JDK without shell-specific PATH hacks.
  if command -v brew >/dev/null 2>&1 && brew --prefix openjdk >/dev/null 2>&1; then
    JDK_LINK="/Library/Java/JavaVirtualMachines/openjdk.jdk"
    JDK_SOURCE="$(brew --prefix openjdk)/libexec/openjdk.jdk"
    if [[ ! -e "$JDK_LINK" ]]; then
      log "registering Homebrew OpenJDK with macOS"
      as_root mkdir -p /Library/Java/JavaVirtualMachines
      as_root ln -sfn "$JDK_SOURCE" "$JDK_LINK"
    fi
  fi
fi

log "environment doctor (external map data intentionally skipped)"
"$VENV/bin/python" -m uralla_build \
  --host "$HOST_CONFIG" \
  doctor --repo-root "$REPO_ROOT" --tools-lock "$REPO_ROOT/config/tools.lock.yaml" \
  --skip-data

cat <<EOF

[setup] READY
[setup] activate: source "$VENV/bin/activate"
[setup] host config: $HOST_CONFIG
[setup] full check after copying map/DEM data:
[setup]   "$VENV/bin/python" -m uralla_build --host "$HOST_CONFIG" doctor --repo-root "$REPO_ROOT"
EOF

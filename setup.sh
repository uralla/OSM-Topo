#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

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

python_is_supported() {
  local candidate="$1"
  [[ -x "$candidate" ]] || return 1
  "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

expand_user_path() {
  local value="$1"
  case "$value" in
    "~") value="$HOME" ;;
    "~/"*) value="$HOME/${value#~/}" ;;
  esac
  printf '%s\n' "$value"
}

OS="$(uname -s)"
IS_WSL=false
if [[ "$OS" == "Linux" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL=true
fi

# One machine-local workspace owns all mutable data and the real host.yaml.
# The Git checkout stores only an ignored pointer to that config.
DEFAULT_WORKSPACE="$HOME/garmin_lab"
if [[ -n "${URALLA_WORKSPACE:-}" ]]; then
  WORKSPACE="$URALLA_WORKSPACE"
  log "working directory from URALLA_WORKSPACE: $WORKSPACE"
elif [[ -n "${URALLA_DATA_ROOT:-}" ]]; then
  # Backward-compatible override for existing scripted installations.
  WORKSPACE="$URALLA_DATA_ROOT"
  log "working directory from URALLA_DATA_ROOT: $WORKSPACE"
elif [[ -t 0 ]]; then
  printf '[setup] Working directory [%s]: ' "$DEFAULT_WORKSPACE"
  IFS= read -r WORKSPACE_INPUT
  WORKSPACE="${WORKSPACE_INPUT:-$DEFAULT_WORKSPACE}"
else
  WORKSPACE="$DEFAULT_WORKSPACE"
  log "non-interactive setup; using default working directory: $WORKSPACE"
fi

WORKSPACE="$(expand_user_path "$WORKSPACE")"
mkdir -p "$WORKSPACE"
WORKSPACE="$(cd "$WORKSPACE" && pwd -P)"

DATA_ROOT="$WORKSPACE"
WORK_ROOT="${URALLA_WORK_ROOT:-$WORKSPACE}"
PUBLISH_ROOT="${URALLA_PUBLISH_ROOT:-$WORKSPACE/output}"
DEM_ROOT="${URALLA_DEM_ROOT:-$WORKSPACE/dem}"
TOOLS_ROOT="${URALLA_TOOLS_ROOT:-$WORKSPACE/tools}"
HOST_CONFIG="${URALLA_HOST_CONFIG:-$WORKSPACE/host.yaml}"
HOST_POINTER="$REPO_ROOT/.uralla-host"

log "working directory: $WORKSPACE"
log "host config: $HOST_CONFIG"

# Python venvs require normal Unix filesystem semantics (notably symlinks).
# WSL repositories are often checked out on Windows drives under /mnt/<drive>,
# where drvfs permissions may prevent `python -m venv` from creating lib64 -> lib.
# Keep the repository wherever the user wants, but place the default venv in the
# Linux filesystem. An explicit URALLA_VENV always wins.
if [[ -n "${URALLA_VENV:-}" ]]; then
  VENV="$URALLA_VENV"
elif [[ "$IS_WSL" == true && "$REPO_ROOT" =~ ^/mnt/[A-Za-z](/|$) ]]; then
  VENV="$HOME/.venvs/osm-topo"
  log "WSL repository is on a Windows-mounted drive; using Linux filesystem for virtualenv: $VENV"
else
  VENV="$REPO_ROOT/.venv"
fi

PYTHON=""
case "$OS" in
  Linux)
    if ! command -v apt-get >/dev/null 2>&1; then
      die "Linux setup currently supports Ubuntu/Debian apt-based hosts"
    fi
    if [[ "$IS_WSL" == true ]]; then
      log "platform: WSL Ubuntu/Debian"
    else
      log "platform: Ubuntu/Debian Linux"
    fi
    log "installing base Python/runtime prerequisites"
    as_root apt-get update
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3 python3-venv python3-pip ca-certificates git
    PYTHON="$(command -v python3 || true)"
    ;;

  Darwin)
    log "platform: macOS"
    command -v brew >/dev/null 2>&1 || die "Homebrew is required; install it from https://brew.sh and rerun setup.sh"

    SYSTEM_PYTHON="$(command -v python3 || true)"
    if [[ -n "$SYSTEM_PYTHON" ]] && python_is_supported "$SYSTEM_PYTHON"; then
      PYTHON="$SYSTEM_PYTHON"
    else
      if [[ -n "$SYSTEM_PYTHON" ]]; then
        log "system python is too old for this project: $($SYSTEM_PYTHON --version 2>&1 || true)"
      else
        log "python3 is not installed"
      fi
      log "installing/updating Python with Homebrew"
      brew install python
      PYTHON="$(brew --prefix)/bin/python3"
      if ! python_is_supported "$PYTHON"; then
        die "Homebrew Python >= 3.11 is required; expected a supported interpreter at $PYTHON"
      fi
    fi
    ;;

  *)
    die "unsupported platform: $OS"
    ;;
esac

[[ -n "$PYTHON" && -x "$PYTHON" ]] || die "python3 is not available after system setup"

PY_MAJOR="$($PYTHON -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$($PYTHON -c 'import sys; print(sys.version_info.minor)')"
if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 11) )); then
  die "Python >= 3.11 is required; found $($PYTHON --version 2>&1)"
fi
log "python: $($PYTHON --version 2>&1) ($PYTHON)"

if [[ ! -x "$VENV/bin/python" ]]; then
  log "creating virtual environment: $VENV"
  mkdir -p "$(dirname "$VENV")"
  "$PYTHON" -m venv "$VENV"
else
  log "virtual environment already exists: $VENV"
fi

log "installing/updating Python project dependencies"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/python" -m pip install -e "$REPO_ROOT"

# The whole mutable workspace hangs from the single user-selected root.
mkdir -p \
  "$DATA_ROOT/input" \
  "$DATA_ROOT/elevation" \
  "$PUBLISH_ROOT" \
  "$PUBLISH_ROOT/mapsource" \
  "$DEM_ROOT" \
  "$TOOLS_ROOT"

if [[ ! -f "$HOST_CONFIG" ]]; then
  log "creating machine-local host config: $HOST_CONFIG"
  mkdir -p "$(dirname "$HOST_CONFIG")"
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
  log "using existing machine-local host config: $HOST_CONFIG"
fi

# Store only a Git-ignored pointer in the checkout. The actual host.yaml remains
# outside Git while normal CLI commands can keep using the historical default.
printf '%s\n' "$HOST_CONFIG" > "$HOST_POINTER.partial"
mv "$HOST_POINTER.partial" "$HOST_POINTER"
log "local host pointer: $HOST_POINTER -> $HOST_CONFIG"

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
    if [[ ! -e "$JDK_LINK" || "$(readlink "$JDK_LINK" 2>/dev/null || true)" != "$JDK_SOURCE" ]]; then
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
[setup] working directory: $WORKSPACE
[setup] host config: $HOST_CONFIG
[setup] full check after copying map/DEM data:
[setup]   "$VENV/bin/python" -m uralla_build doctor --repo-root "$REPO_ROOT"
[setup] build example (host config is resolved automatically):
[setup]   "$VENV/bin/python" -m uralla_build build-product crimea --apply
EOF

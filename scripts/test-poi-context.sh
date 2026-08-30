#!/usr/bin/env bash
set -Eeuo pipefail

# Full product build with a compact POI-context diagnostic extract.
# Usage:
#   bash scripts/test-poi-context.sh [product]
# Default: crimea

PRODUCT="${1:-crimea}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs/poi-context"
STAMP="$(date '+%Y%m%d-%H%M%S')"
FULL_LOG="$LOG_DIR/${PRODUCT}-${STAMP}.log"
POI_LOG="$LOG_DIR/${PRODUCT}-${STAMP}.poi.txt"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

python_is_usable() {
    local candidate="$1"
    command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]] || return 1
    "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1 || return 1
    "$candidate" -c 'import yaml, osmium' >/dev/null 2>&1 || return 1
    return 0
}

if command -v uralla-build >/dev/null 2>&1; then
    BUILD_CMD=(uralla-build build-product "$PRODUCT" --repo-root "$REPO_ROOT" --apply --no-resume)
    RUNTIME="$(command -v uralla-build)"
else
    PYTHON_BIN=""
    for candidate in \
        "$REPO_ROOT/.venv/bin/python" \
        "$REPO_ROOT/venv/bin/python" \
        python3.13 python3.12 python3.11 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        python3 python
    do
        if python_is_usable "$candidate"; then
            PYTHON_BIN="$candidate"
            break
        fi
    done

    if [[ -z "$PYTHON_BIN" ]]; then
        printf 'ERROR: no usable Python environment found.\n' >&2
        printf 'OSM-Topo requires Python >= 3.11 with PyYAML and osmium installed.\n' >&2
        printf '\nRecommended one-time setup on macOS:\n' >&2
        printf '  brew install python@3.12\n' >&2
        printf '  /opt/homebrew/bin/python3.12 -m venv .venv\n' >&2
        printf '  .venv/bin/python -m pip install -e .\n' >&2
        printf '\nThen run this script again.\n' >&2
        exit 2
    fi

    BUILD_CMD=("$PYTHON_BIN" -m uralla_build build-product "$PRODUCT" --repo-root "$REPO_ROOT" --apply --no-resume)
    RUNTIME="$($PYTHON_BIN -c 'import sys; print(sys.executable + " (Python " + sys.version.split()[0] + ")")')"
fi

printf 'POI context diagnostic build\n'
printf 'Product: %s\n' "$PRODUCT"
printf 'Runtime: %s\n' "$RUNTIME"
printf 'Full log: %s\n' "$FULL_LOG"
printf 'POI extract: %s\n\n' "$POI_LOG"

START_EPOCH=$(date +%s)
set +e
"${BUILD_CMD[@]}" 2>&1 | tee "$FULL_LOG"
BUILD_STATUS=${PIPESTATUS[0]}
set -e
END_EPOCH=$(date +%s)
ELAPSED=$((END_EPOCH - START_EPOCH))

# Keep only the lines useful for tuning the context classifier. The full log is
# retained next to this compact extract for timing/error analysis.
grep -E \
    'POI context:|POI activity density:|POI activity classifier:|POI activity matrix:|POI activity sample:|POI accommodation check:|POI accommodation:|\[preprocess\].*(objects|done)|BUILD (COMPLETE|FAILED)|TOTAL' \
    "$FULL_LOG" > "$POI_LOG" || true

printf '\n============================================================\n'
printf 'POI CONTEXT EXTRACT\n'
printf '============================================================\n'
cat "$POI_LOG"
printf '============================================================\n'
printf 'Build exit status: %d\n' "$BUILD_STATUS"
printf 'Wall time: %02d:%02d:%02d\n' $((ELAPSED / 3600)) $(((ELAPSED % 3600) / 60)) $((ELAPSED % 60))
printf 'Full log: %s\n' "$FULL_LOG"
printf 'POI extract: %s\n' "$POI_LOG"

exit "$BUILD_STATUS"

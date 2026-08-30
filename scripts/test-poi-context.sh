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

if command -v uralla-build >/dev/null 2>&1; then
    BUILD_CMD=(uralla-build build-product "$PRODUCT" --repo-root "$REPO_ROOT" --apply --no-resume)
else
    BUILD_CMD=(python -m uralla_build build-product "$PRODUCT" --repo-root "$REPO_ROOT" --apply --no-resume)
fi

printf 'POI context diagnostic build\n'
printf 'Product: %s\n' "$PRODUCT"
printf 'Full log: %s\n' "$FULL_LOG"
printf 'POI extract: %s\n\n' "$POI_LOG"

set +e
"${BUILD_CMD[@]}" 2>&1 | tee "$FULL_LOG"
BUILD_STATUS=${PIPESTATUS[0]}
set -e

# Keep only the lines useful for tuning the context classifier. The full log is
# retained next to this compact extract for timing/error analysis.
grep -E \
    'POI context:|POI activity density:|POI accommodation check:|POI accommodation:|\[preprocess\].*(objects|done)|BUILD (COMPLETE|FAILED)|TOTAL' \
    "$FULL_LOG" > "$POI_LOG" || true

printf '\n============================================================\n'
printf 'POI CONTEXT EXTRACT\n'
printf '============================================================\n'
cat "$POI_LOG"
printf '============================================================\n'
printf 'Build exit status: %d\n' "$BUILD_STATUS"
printf 'Full log: %s\n' "$FULL_LOG"
printf 'POI extract: %s\n' "$POI_LOG"

exit "$BUILD_STATUS"

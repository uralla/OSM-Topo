#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DEM_SOURCE="$SCRIPT_DIR"
DEM_LIST="$SCRIPT_DIR/dem-required-files.txt"
DEM_TARGET="$SCRIPT_DIR/OSM"

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

human_size() {
    numfmt --to=iec-i --suffix=B "$1" 2>/dev/null || printf '%s bytes\n' "$1"
}

[[ -f "$DEM_LIST" ]] || die "list not found: $DEM_LIST"
[[ -r "$DEM_LIST" ]] || die "list is not readable: $DEM_LIST"

total_files=0
total_bytes=0
missing_files=0
invalid_lines=0

printf 'Checking source files listed in %s ...\n' "$(basename -- "$DEM_LIST")"

while IFS= read -r relative_path || [[ -n "$relative_path" ]]; do
    relative_path="${relative_path%$'\r'}"
    [[ -n "$relative_path" ]] || continue

    case "$relative_path" in
        /*|.|..|./*|../*|*/../*|*/..|OSM|OSM/*)
            printf 'INVALID\t%s\n' "$relative_path" >&2
            invalid_lines=$((invalid_lines + 1))
            continue
            ;;
    esac

    source_file="$DEM_SOURCE/$relative_path"
    if [[ ! -s "$source_file" ]]; then
        printf 'MISSING\t%s\n' "$relative_path" >&2
        missing_files=$((missing_files + 1))
        continue
    fi

    total_files=$((total_files + 1))
    file_size="$(stat -c '%s' -- "$source_file")"
    total_bytes=$((total_bytes + file_size))
done < "$DEM_LIST"

(( invalid_lines == 0 )) || die "$invalid_lines unsafe path(s) found in the list"
(( missing_files == 0 )) || die "$missing_files source file(s) are missing or empty; nothing was copied"
(( total_files > 0 )) || die "the list contains no files"

printf 'Ready to copy: %s files, %s\n' "$total_files" "$(human_size "$total_bytes")"
printf 'Source: %s\n' "$DEM_SOURCE"
printf 'Target: %s\n' "$DEM_TARGET"

mkdir -p -- "$DEM_TARGET"

if command -v rsync >/dev/null 2>&1; then
    rsync -a --info=progress2 --stats \
        --files-from="$DEM_LIST" \
        -- "$DEM_SOURCE"/ "$DEM_TARGET"/
else
    printf 'rsync is not installed; copying with cp without an overall progress indicator.\n'
    copied=0
    while IFS= read -r relative_path || [[ -n "$relative_path" ]]; do
        relative_path="${relative_path%$'\r'}"
        [[ -n "$relative_path" ]] || continue
        target_file="$DEM_TARGET/$relative_path"
        mkdir -p -- "$(dirname -- "$target_file")"
        cp -a -- "$DEM_SOURCE/$relative_path" "$target_file"
        copied=$((copied + 1))
        if (( copied % 100 == 0 || copied == total_files )); then
            printf 'Copied: %s/%s files\n' "$copied" "$total_files"
        fi
    done < "$DEM_LIST"
fi

verification_errors=0
while IFS= read -r relative_path || [[ -n "$relative_path" ]]; do
    relative_path="${relative_path%$'\r'}"
    [[ -n "$relative_path" ]] || continue
    source_file="$DEM_SOURCE/$relative_path"
    target_file="$DEM_TARGET/$relative_path"
    if [[ ! -s "$target_file" ]]; then
        printf 'COPY_MISSING\t%s\n' "$relative_path" >&2
        verification_errors=$((verification_errors + 1))
    elif [[ "$(stat -c '%s' -- "$source_file")" != "$(stat -c '%s' -- "$target_file")" ]]; then
        printf 'SIZE_MISMATCH\t%s\n' "$relative_path" >&2
        verification_errors=$((verification_errors + 1))
    fi
done < "$DEM_LIST"

(( verification_errors == 0 )) || die "$verification_errors copied file(s) failed verification"

printf 'Done: %s files copied and verified in %s\n' "$total_files" "$DEM_TARGET"
du -sh -- "$DEM_TARGET"

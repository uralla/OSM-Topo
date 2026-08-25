# Portable DEM subset

The committed lists are generated from `config/maps.yaml`, the active product
polygons, and `dem-files.tsv`.

- `config/dem-required-files-exact.txt` contains available HGT cells whose
  one-degree rectangles intersect an enabled product with non-null `elevation`.
- `config/dem-required-files.txt` is the recommended portable set. It adds one
  available HGT cell around the exact selection for boundary processing and
  small polygon changes.
- `config/dem-selection-report.json` records counts, byte sizes, products,
  polygons, and intersecting cells absent from the source inventory.

Only `*.hgt` data files are copied. GDAL `*.AUX.xml`, `DIR`, inventory files,
and helper scripts are not required for HGT elevation data and are excluded.

## Regenerate lists

```bash
python -m uralla_build select-dem \
  --inventory dem-files.tsv \
  --halo 1 \
  --output config/dem-required-files.txt \
  --exact-output config/dem-required-files-exact.txt \
  --report config/dem-selection-report.json
```

## Copy safely on Ubuntu

Adjust only the source and target paths:

```bash
DEM_SOURCE="/mnt/nod/dem"
DEM_TARGET="/mnt/nod/dem-uralla"
DEM_LIST="$PWD/config/dem-required-files.txt"

test -d "$DEM_SOURCE" || { echo "Source not found: $DEM_SOURCE"; exit 1; }
test -f "$DEM_LIST" || { echo "List not found: $DEM_LIST"; exit 1; }
test "$(realpath -m "$DEM_SOURCE")" != "$(realpath -m "$DEM_TARGET")" || {
  echo "Source and target must be different"
  exit 1
}

mkdir -p "$DEM_TARGET"

rsync -a --dry-run --itemize-changes \
  --files-from="$DEM_LIST" \
  -- "$DEM_SOURCE"/ "$DEM_TARGET"/
```

If the dry run shows only the expected HGT files, perform the copy:

```bash
rsync -a --info=progress2 \
  --files-from="$DEM_LIST" \
  -- "$DEM_SOURCE"/ "$DEM_TARGET"/
```

Verify every listed file exists and is non-empty:

```bash
DEM_TARGET="/mnt/nod/dem-uralla"
DEM_LIST="$PWD/config/dem-required-files.txt"

while IFS= read -r DEM_FILE; do
  test -s "$DEM_TARGET/$DEM_FILE" || printf 'MISSING\t%s\n' "$DEM_FILE"
done < "$DEM_LIST"

printf 'Expected files: %s\n' "$(wc -l < "$DEM_LIST")"
printf 'Copied HGT files: %s\n' "$(find "$DEM_TARGET" -type f -iname '*.hgt' | wc -l)"
du -sh -- "$DEM_TARGET"
```

No command removes or modifies files in the source DEM directory.

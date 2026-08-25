# Semantic preprocessor

## Position in the pipeline

The preprocessor runs after polygon extraction and the existing place-tag
transformation, but before external elevation data is merged and before
splitter. This keeps generated contour objects outside semantic filtering and
ensures that every enriched or filtered OSM object reaches all resulting
tiles.

The first implemented profile is `ru-political-parties`. It is selected in
`config/maps.yaml` for the `russia`, `northwestern` and `crimea` sources. Other
products are unchanged.

## Blacklist behaviour

Rules live in `config/preprocessor-blacklist.yaml`, not in Python or the mkgmap
style. The first catalogue entries are:

| Rule | Wikidata | Additional matching |
|---|---|---|
| `united-russia` | `Q151469` | Russian cases, English/transliterated names, `ЕдРо`, `er.ru` |
| `cprf` | `Q192187` | full Russian name and cases, `КПРФ`, `KPRF`, English name, `kprf.ru` |

OSM party offices normally use `office=political_party` together with
`political_party=*`. Stable Wikidata IDs are preferred when present.

Two actions preserve OSM structural integrity:

1. `neutralize` removes every tag from an identified party object. The node,
   way or relation remains available as a geometry/reference primitive, so a
   shared building way or relation membership is not broken.
2. `scrub` removes only matching tags from an otherwise unrelated object. For
   example, a road retains `highway` and `surface` while a matching `name` or
   `description` is removed.

The ambiguous abbreviation `ЕР` is deliberately not a standalone alias. It
has too many unrelated uses and would create broad false positives. Stable
Wikidata, full names, their grammatical forms, `ЕдРо` and the official domain
cover the intended party data without that risk.

All tag values are scanned, including localized names, description,
Wikipedia, website, operator and brand fields. After writing, the output PBF is
read a second time with the same rules. Any remaining match fails the stage;
therefore mkgmap never receives an unverified PBF.

## Reports

Each preprocessor stage creates `report.json` next to
`preprocessed.osm.pbf`. It records:

- selected profiles and rule IDs;
- objects scanned;
- objects neutralized or scrubbed;
- number of removed tags;
- hit counts by rule;
- up to 100 object/type/action samples without copying the removed text;
- the required `verified_forbidden_tags: 0` result.

## Standalone command

```sh
python3 -m uralla_build preprocess \
  --input source.osm.pbf \
  --output filtered.osm.pbf \
  --config config/preprocessor-blacklist.yaml \
  --profile ru-political-parties \
  --report report.json
```

Normal builds do not call this manually. `build-product` inserts the stage from
the source-to-profile mapping in the manifest.

The implementation uses streaming pyosmium processing and atomic output
replacement. The package is declared as a project dependency and is available
as binary wheels for the supported Ubuntu and Apple Silicon macOS hosts.

References:

- [OSM `office=political_party`](https://wiki.openstreetmap.org/wiki/Tag:office%3Dpolitical_party)
- [OSM `political_party=*`](https://wiki.openstreetmap.org/wiki/Key:political_party)
- [pyosmium writing modified objects](https://docs.osmcode.org/pyosmium/latest/user_manual/06-Writing-Data/)
- [Wikidata Q151469](https://www.wikidata.org/wiki/Q151469)
- [Wikidata Q192187](https://www.wikidata.org/wiki/Q192187)

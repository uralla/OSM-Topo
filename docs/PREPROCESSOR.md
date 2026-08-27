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

## Future: semantic geographic-name cleanup and compact labels

Add a conservative semantic name-normalization stage for geographic objects.
Its purpose is to remove obvious renderer-oriented type words that have been
incorrectly placed at the beginning of `name=*`, while avoiding edits to real
toponyms.

Normalization must be object-type aware. Examples:

- `natural=ridge`: `хребет Нурали`, `Хребет Нурали`, `хр. Нурали`, `хр Нурали`
  -> render as `Нурали`;
- `natural=peak` / `natural=volcano`: `гора Ямантау`, `Г. Ямантау`, `г Ямантау`
  -> render as `Ямантау`;
- lake/water objects: `озеро Тургояк`, `Оз. Тургояк`, `оз Тургояк`
  -> render as `Тургояк`;
- `natural=waterfall`: leading renderer-oriented forms such as `водопад`,
  `Водопад`, `вод.`, `вод`, `вдп.`, `вдп` should be eligible for removal when
  they are clearly a type token rather than part of the proper name.

Only a leading type token is eligible for automatic removal. A trailing word
that can legitimately be part of the proper name must be preserved. For
example, `Гора Большая` may be normalized to `Большая`, but `Большая Гора`
must remain unchanged. The same principle applies to names such as `Белая
Гора`, `Черное Озеро` and `Каменный Хребет`.

Support common capitalization and punctuation variants (`гора`, `Гора`, `г.`,
`г`, `озеро`, `Озеро`, `оз.`, `оз`, `хребет`, `Хребет`, `хр.`, `хр`,
`водопад`, `Водопад`, `вод.`, `вод`, `вдп.`, `вдп`) only when they agree with
the OSM object type. Do not use a global regular expression that strips these
words from unrelated objects.

Keep the original OSM `name=*` available for object inspection/search. The
cleaned value should be stored in a separate render-only tag (for example
`uralla:label=*`) rather than silently overwriting the source name. This makes
mapping errors visible when the user selects an object and allows later OSM
correction.

The same render-only label path can provide semantic compacting of common
geographic adjectives where it is safe and useful on a topo map, for example:

- `Большой Шелом` -> `Б. Шелом`;
- `Малый Ямантау` -> `М. Ямантау`.

Do not add `Большой=>Б.` / `Малый=>М.` to the existing global `inc/name`
substitution block, because that block applies to points, lines and polygons
of every kind and would also abbreviate unrelated proper names such as towns,
streets or organizations. Compacting must be scoped to agreed geographic
object classes.

## Future: regional display-language fallback

Add a separate render-label policy for regions where the default OSM `name=*`
occasionally uses a local-language form that is inconvenient or unreadable on
the target Garmin map, while a suitable Russian localized name is already
present.

This must not rewrite or delete the source `name=*`. The preferred implementation
is to populate the same render-only tag used by the geographic-name cleanup,
for example `uralla:label=*`.

For Russian map products, including multilingual republics such as
Bashkortostan, use the following conservative precedence when a Russian display
label is desired:

1. if `name:ru=*` exists and is non-empty, it may be used as `uralla:label`;
2. otherwise fall back to the original `name=*` unchanged;
3. never invent a translation, transliterate automatically, or infer a Russian
   name from spelling alone.

The raw `name=*` must remain available in object properties/search so that a
mapper can see the original OSM value and identify questionable tagging later.
The display-language fallback is a cartographic presentation decision, not an
attempt to rewrite OSM data.

Optionally, the preprocessor may report suspicious cases for later inspection,
for example when a feature in a Russian product has a non-Russian `name=*` but
also has a distinct `name:ru=*`. Such reporting should be diagnostic only and
must not by itself trigger destructive edits.

Do not implement a blanket rule such as "all names inside Russia must be
Russian". OSM explicitly allows the default `name=*` to follow local naming
practice, and multilingual regions can contain legitimate non-Russian default
names. The safe signal is the presence of an explicit localized tag such as
`name:ru=*`, not guessed language from geography alone.

Any implementation of these future naming sections changes preprocessor
output, so testing requires a full rebuild through the preprocessing stage;
rebuilding only the style against an older intermediate PBF is insufficient.

References:

- [OSM names](https://wiki.openstreetmap.org/wiki/Name)
- [OSM `office=political_party`](https://wiki.openstreetmap.org/wiki/Tag:office%3Dpolitical_party)
- [OSM `political_party=*`](https://wiki.openstreetmap.org/wiki/Key:political_party)
- [pyosmium writing modified objects](https://docs.osmcode.org/pyosmium/latest/user_manual/06-Writing-Data/)
- [Wikidata Q151469](https://www.wikidata.org/wiki/Q151469)
- [Wikidata Q192187](https://www.wikidata.org/wiki/Q192187)

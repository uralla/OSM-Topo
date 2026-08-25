# Static landmark catalogues

These catalogues exist only to keep a small set of useful geographic reference points visible on distant Garmin zoom levels. They are deliberately static and are expected to be refreshed infrequently rather than queried from online services during a normal map build.

## Peaks and volcanoes

`peak-landmarks.tsv` is a manually maintained lookup table for selected well-known peaks and volcanoes.

The normal map build must not query Wikidata. Peak matching is by the OSM `wikidata=Q...` tag only. The `name` column is informational and the `origin` column records whether an entry came from the legacy hard-coded style list or was added during catalogue expansion.

## Rivers

`river-landmarks.tsv` contains selected large rivers plus the legacy author-selected river core. It stores an approximate published length and a stable display rank:

- rank 1: 3000 km or longer;
- rank 2: 1500-2999 km;
- rank 3: 750-1499 km;
- rank 4: shorter rivers retained from the legacy author-selected landmark set.

River ways are matched by normalized `name`, `name:ru`, `name:en`, or `int_name` against the canonical name and aliases in the catalogue. This intentionally avoids relation-member propagation: the purpose is distant-zoom visual orientation, not a complete hydrological model.

Existing hard-coded peak and river style rules remain in place as fallbacks until catalogue-based rendering has been visually checked on current map products.

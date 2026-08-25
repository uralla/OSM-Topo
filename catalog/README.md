# Static landmark catalogues

`peak-landmarks.tsv` is a manually maintained lookup table for selected well-known peaks and volcanoes that should remain visible on distant Garmin zoom levels.

The normal map build must not query Wikidata. Matching is by the OSM `wikidata=Q...` tag only. The `name` column is informational and the `origin` column records whether an entry came from the legacy hard-coded style list or was added during catalogue expansion.

Existing hard-coded style rules remain in place until catalogue-based rendering has been integrated and visually checked on current map products.

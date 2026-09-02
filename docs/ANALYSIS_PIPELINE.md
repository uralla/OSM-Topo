# Analyze/apply preprocessor architecture

Goal: separate expensive spatial analysis from the fast application of derived tags to a fresh OSM PBF.

Planned independent analysis artifacts:

- road density;
- POI context;
- activity/screen-pressure context;
- synthetic area POIs.

The analysis artifacts may be generated independently and, where resources allow, in parallel. A later apply stage reads a fresh OSM PBF once, applies all available cached hints, inserts synthetic POIs, and writes the prepared PBF used by the normal Garmin build.

The first implementation target is road density because its current spatial analysis is expensive and its final result can be represented compactly as a mapping from way ID to render class and density level.

The existing preprocess pipeline remains the reference path until the new analyze/apply path is benchmarked on a large map such as `ural-s`.

## Area POI merge policy

Area analysis now distinguishes three outcomes for an approved closed-way POI:

1. no compatible real node: create the synthetic centre POI;
2. exactly one compatible node inside the area, or within 8 metres of its boundary:
   keep the real node, copy only its missing useful tags from the area, and do not
   create a synthetic POI;
3. several compatible nodes: do not guess, do not enrich any node, and suppress the
   synthetic POI as an ambiguous duplicate.

The node's own tags always win. Building/roof/source geometry tags are not copied.
Accommodation types share one family, all approved `shop=*` types share `retail`,
ordinary food/drink types share `food`, and `clinic`/`doctors` share one medical
family across `amenity=*` and `healthcare=*`. Other categories stay exact by
default. In particular, `bank` does not match `atm`, `fuel` does not match an
on-site shop, and education/public-service/tourism-attraction types do not merge
across unrelated subtypes.

Reusable area artifacts store both source-way and target-node OSM versions. APPLY
uses enrichment only when both objects are unchanged; otherwise it reports a stale
skip and waits for the next ANALYZE.

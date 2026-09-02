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

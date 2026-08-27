# Uralla automated build system

## Status and authority

This document is the implementation specification for the replacement of the
legacy regional shell scripts in `scripts/`.

The legacy scripts are migration input only. They are not the future runtime,
are not to be expanded with new regions, and are not the place for fixes to
shared build logic.

The authoritative sources are:

1. `config/maps.yaml` for map products and their stable identities;
2. this document for pipeline behaviour and invariants;
3. `docs/reviews/STYLE_REVIEW_MASTER.md` for cartographic and audit decisions;
4. Git history for versions of style, TYP, preprocessor and build code.

Previously supplied ZIP archives are not build inputs or reference sources.

## Implementation checkpoint

Implemented in `main`:

- migrated 27-product manifest at `config/maps.yaml`;
- static manifest, FID/PID, overview and reserved-block validation;
- splitter `areas.list` and `template.args` range validation;
- human-readable and JSON CLI output;
- read-only host doctor with a temporary atomic-rename probe;
- dry-run-first Ubuntu/macOS bootstrap and pinned tool installer;
- resumable shell-free product plans covering extract, transform, elevation
  merge, splitter, range validation, mkgmap and atomic publication;
- streaming OSM PBF blacklist preprocessor, enabled for Russian source
  profiles before elevation merge and splitter;
- 56-test suite, including a real pyosmium PBF write/read verification test.

Current commands:

```sh
python3 -m uralla_build validate-manifest
python3 -m uralla_build validate-areas PRODUCT areas.list --template template.args
cp config/host.example.yaml config/host.yaml
python3 -m uralla_build doctor
python3 -m uralla_build bootstrap
python3 -m uralla_build bootstrap --apply --capture-checksums
python3 -m uralla_build build-product ural-n
python3 -m uralla_build preprocess --input input.osm.pbf \
  --output output.osm.pbf --config config/preprocessor-blacklist.yaml \
  --profile ru-political-parties --report blacklist-report.json
python3 -m unittest discover -s tests -v
```

`bootstrap` is a plan-only command unless `--apply` is supplied. The first
official archive admission additionally requires `--capture-checksums`; the
resulting `config/tools.lock.yaml` diff must be reviewed and committed. Later
downloads must match the captured digest exactly.

## Frozen project decisions

- Preserve the existing product boundaries, names, FID/PID values and first
  tile map IDs while migrating.
- Replace the duplicated regional scripts with one manifest-driven runner.
- Schedule maps by product priority first and overdue age second.
- Optimise for map quality and reliability. A full build lasting about one day
  on the throttled reserve Ubuntu computer is acceptable.
- Record measurements and tune memory, splitter `max-nodes`, mkgmap jobs and
  ordering from real build history rather than guesses.
- Run the semantic preprocessor before splitter.
- Publish ready IMG and GMAPI/MapSource packages through the existing Syncthing
  ready-files tree.
- Publish atomically and retain the previous valid release if any stage fails.
- Pin project versions of splitter and mkgmap.
- Bootstrap/doctor supports Ubuntu through apt and macOS through Homebrew.
- Large DEM and pre-generated elevation inputs are externally synchronised;
  doctor validates them but does not download or regenerate them.
- Split ZIP volumes are forbidden. IMG is published directly without an
  archive; GMAPI/MapSource is published as one uncompressed/store ZIP.

## Product model

Each active product has one manifest record containing:

- stable product key and enabled state;
- scheduling priority and update interval;
- source PBF, polygon, optional contour/elevation PBF and GeoNames input;
- FID, PID, overview ID and reserved tile-ID block;
- family, series, overview and output names;
- splitter parameters and explicit per-map overrides;
- publication targets.

Defaults may be inherited, but identity fields must be explicit. The runner
must never derive or silently renumber an existing identity during a normal
build.

## Pipeline

The normal per-product pipeline is:

```text
select product from queue
  -> validate manifest and required inputs
  -> update/download shared source PBF
  -> extract product polygon
  -> apply place/address transformation
  -> semantic preprocessor
  -> merge externally supplied elevation/contour PBF, when configured
  -> splitter
  -> tile-range validation
  -> mkgmap
  -> package validation
  -> atomic publish to Syncthing ready-files tree
  -> record successful release and metrics
```

The semantic preprocessor runs before elevation merge so it sees the actual OSM
objects, not generated contour geometry. Its enriched tags are present before
splitter cuts the product into tiles.

Every stage writes to a build-specific workspace. A failed build must not
modify the published release.

## Semantic preprocessor contract

The first implemented profile is the configurable Russian political-party
blacklist in `config/preprocessor-blacklist.yaml`. It currently removes map
references to United Russia and the Communist Party of the Russian Federation
from products based on the `russia`, `northwestern` and `crimea` sources.

The blacklist scans every OSM tag value, using stable Wikidata IDs, controlled
aliases, inflection-aware patterns and official domains. A party object is
neutralised by removing all of its tags while retaining the primitive as
untagged geometry, so node/way/relation references cannot be broken. On an
otherwise unrelated object only the matching tags are removed. The output PBF
is scanned again with the same rules; any remaining forbidden tag fails the
stage. Ambiguous standalone abbreviations such as `ЕР` are deliberately not
matched because they produce false positives.

The next catalogue phase covers rivers and peaks without recalculating
published geographic facts.

Rivers:

- catalogue published river importance/length data;
- match primarily by `wikidata=Q...`;
- inspect `type=waterway` relations before splitting;
- propagate rank to the required member ways;
- write `uralla:river_rank=1..4`;
- write `uralla:manual_keep=yes` for the mandatory author core;
- preserve the current 29 author-selected rivers as the mandatory seed set.

Peaks and volcanoes:

- use published height, prominence, isolation and importance data;
- match `natural=peak|volcano` primarily by Wikidata;
- use controlled fallback by normalised name and coordinates;
- write `uralla:peak_rank=1..4`;
- write `uralla:manual_keep=yes` for the mandatory author core;
- preserve the current author-selected notable peaks.

The catalogue is designed for Europe and Asia from the start so new maps can
reuse it. Existing hard-coded style name lists remain until the catalogue is
validated on current products.

## Identity and range rules

All map IDs are represented as quoted eight-digit strings in the manifest.

Two existing schemes are preserved during migration:

| Scheme | Overview ID | First tile | Last reserved tile | Capacity |
|---|---:|---:|---:|---:|
| legacy | `FID*1000` | `+1` | `+999` | 999 |
| current | `FID*10000` | `+1` | `+9999` | 9999 |

The common mkgmap default overview number `63240000` is forbidden for active
products. Each product receives the overview ID at the start of its own block.

Before splitter, the validator checks:

- product keys, FID/PID pairs and overview IDs are unique;
- overview and tile IDs are exactly eight decimal digits;
- reserved blocks do not overlap;
- first and last tile lie inside the declared block;
- referenced polygon and inputs exist.

After splitter, it reads `areas.list` and `template.args` and checks:

- first and last generated map IDs;
- tile count and continuity;
- no ID reaches the next product block;
- no overview ID appears among normal tiles;
- file names agree with internal IDs.

After mkgmap, it checks all generated IMG/TDB/TYP artifacts, including final
FID/PID and duplicate internal map IDs.

## Stable splitter areas

Each product owns a versioned `areas.list` path. Once a successful baseline is
accepted, regular updates pass it to splitter through `--split-file`.

Regeneration is a deliberate operation, not an automatic side effect. It must:

1. create a new candidate areas file;
2. validate the candidate tile range;
3. compare count and coverage with the previous version;
4. record the identity change in build history;
5. replace the active file only after a successful package build.

## Scheduling and concurrency

The queue ordering is:

1. higher product priority;
2. greater overdue age relative to the configured update interval;
3. stable product key as deterministic tie-breaker.

The initial product-level concurrency is one build at a time on the reserve
Ubuntu host. Internal splitter/mkgmap concurrency remains configurable and is
tuned from measurements. A global lock prevents two schedulers from publishing
simultaneously.

Manual runs use the same queue and pipeline; they do not bypass validation.

## Build history and measurements

For every build and every stage record:

- product key, build ID, start/end time and duration;
- success/failure, exit code and failure stage;
- command/tool version without secrets;
- source timestamp/checksum and input/output sizes;
- style, TYP, build-system and preprocessor Git revisions;
- host, OS, Java version and relevant environment limits;
- CPU time/utilisation;
- peak RAM;
- peak swap and major/minor page faults;
- disk read/write volume;
- splitter tile count, first/last ID and warnings;
- mkgmap warnings and produced artifact sizes.

History must remain readable after workspaces are cleaned. It is the basis for
changing heap sizes, `max-nodes`, internal jobs and queue ordering.

## Failure and publication policy

- A stage failure stops that product build.
- Other products remain eligible for later queue processing.
- The failed workspace and logs are retained according to the cleanup policy.
- A retry creates a new build record and may reuse only validated checkpoints.
- Ready files are written under temporary names/directories.
- Validation completes before publication.
- Atomic rename promotes the complete release.
- The last valid release remains untouched on failure.
- IMG and GMAPI/MapSource outputs from one build are promoted together.

The initial publication root is the existing `/mnt/nod/garmin` Syncthing tree,
with the MapSource/GMAPI package under its existing `mapsource` subdirectory.
The path is host configuration, not repeated in every product record.

Publication format is fixed:

- one ready `.img` file, not wrapped in ZIP;
- one GMAPI/MapSource store ZIP;
- no `zip -s` split volumes;
- temporary names during assembly and one atomic promotion after validation.

## Bootstrap and doctor

`bootstrap` installs or prepares small reproducible dependencies:

- Java runtime required by pinned mkgmap/splitter;
- osmium-tool;
- osmosis or the chosen equivalent transformation runtime;
- archive utilities;
- the build runner's own dependencies.

On Ubuntu it uses apt; on macOS it uses Homebrew. It must show the proposed
changes and fail clearly when package installation needs user authority.

`doctor` is read-only and validates:

- supported OS and architecture;
- free disk space and writable work/publish paths;
- Java and native tool versions;
- the Python `osmium` module required by the streaming preprocessor;
- pinned splitter/mkgmap artifacts and checksums;
- style/TYP/args presence;
- source, bounds, sea, GeoNames, polygon, DEM and elevation inputs;
- manifest and identity invariants;
- Syncthing publication directories;
- ability to create and atomically rename a small test file in a temporary
  validation directory.

Doctor never downloads the large DEM/elevation datasets.

Machine-specific roots are stored in ignored `config/host.yaml`, created from
`config/host.example.yaml`. Manifest paths under `input/` and `elevation/` are
resolved below `data_root`; local `poly/` data and repository-owned `styles/`
and `scripts/` paths remain relative to the checkout. This replaces hard-coded
DEM paths.

## Migration acceptance

Migration is complete only when:

- all 27 current products exist in the manifest;
- all legacy IDs, product boundaries, names and material per-map options are
  accounted for;
- Georgia is actually selected and built, eliminating the legacy
  `/georgia.sh` orchestration failure;
- validator passes every reserved range;
- a representative small, medium and large product build successfully;
- published IMG and GMAPI/MapSource artifacts pass validation;
- the old scripts are no longer used by scheduling or publication.

Legacy scripts may remain temporarily for audit history, but they are outside
the working build path.

## Implementation order

1. Commit this specification and the migrated product manifest.
2. Implement manifest schema validation and identity/range validation.
3. Implement doctor/bootstrap checks.
4. Implement the common stage runner and build history.
5. Implement queue scheduling and atomic publication.
6. Migrate and validate representative products.
7. Extend the implemented blacklist preprocessor with the Eurasia river/peak
   catalogue and rank enrichment.
8. Switch style rules from hard-coded names to validated `uralla:*_rank` tags.
9. Remove legacy scripts from the operational workflow.

"""Parallel reusable analysis bundle and one-pass application to fresh OSM."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import time
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .area_pois import AreaPoiEnrichment, SyntheticAreaPoi
from .errors import StageError
from .poi_context_analysis import (
    _CONTEXT_TAGS,
    _signature,
    load_poi_context_analysis,
    analyze_poi_context,
)
from .preprocessor import _load_osmium
from .road_density import ROAD_DENSITY_CLASS_TAG, ROAD_DENSITY_TAG, road_density_class
from .road_density_analysis import analyze_road_density, load_road_density_analysis


def _analyze_worker(kind: str, source: str, output: str) -> tuple[str, float, dict[str, object]]:
    started = time.monotonic()
    osmium = _load_osmium()
    if kind == "road_density":
        stats = analyze_road_density(source, output, osmium)
    elif kind == "poi_context":
        stats = analyze_poi_context(source, output, osmium)
    else:
        raise ValueError(f"unknown analysis kind: {kind}")
    return kind, time.monotonic() - started, stats


def analyze_bundle(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    workers: int = 2,
    reporter: Any = None,
) -> dict[str, object]:
    """Build independent road/POI artifacts concurrently in separate processes."""
    source = Path(input_path).resolve()
    target_dir = Path(output_dir).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"analysis input is missing or empty: {source}")
    target_dir.mkdir(parents=True, exist_ok=True)
    jobs = {
        "road_density": target_dir / "road-density.json.gz",
        "poi_context": target_dir / "poi-context.json.gz",
    }
    started = time.monotonic()
    results: dict[str, object] = {}
    max_workers = max(1, min(int(workers), len(jobs)))
    if reporter is not None:
        reporter(f"Analysis bundle: {len(jobs)} jobs, {max_workers} workers")
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_analyze_worker, kind, str(source), str(path)): kind
            for kind, path in jobs.items()
        }
        for future in as_completed(futures):
            kind, elapsed, stats = future.result()
            results[kind] = {
                "seconds": round(elapsed, 3),
                "artifact": str(jobs[kind]),
                "stats": stats,
            }
            if reporter is not None:
                reporter(f"Analysis bundle: {kind} ready in {elapsed:.1f}s")
    results["wall_seconds"] = round(time.monotonic() - started, 3)
    if reporter is not None:
        reporter(f"Analysis bundle complete in {float(results['wall_seconds']):.1f}s")
    return results


def _load_road_hints(path: str | Path) -> dict[int, tuple[str, str]]:
    payload = load_road_density_analysis(path)
    raw = payload["ways"]
    assert isinstance(raw, dict)
    result: dict[int, tuple[str, str]] = {}
    for raw_id, value in raw.items():
        if not isinstance(raw_id, str) or not isinstance(value, list) or len(value) != 2:
            continue
        try:
            way_id = int(raw_id)
        except ValueError:
            continue
        render_class, level = str(value[0]), str(value[1])
        if level not in {"dense", "very_dense"}:
            continue
        result[way_id] = (render_class, level)
    return result


def _load_poi_hints(path: str | Path) -> dict[int, tuple[dict[str, str], dict[str, str]]]:
    payload = load_poi_context_analysis(path)
    raw = payload["nodes"]
    assert isinstance(raw, dict)
    result: dict[int, tuple[dict[str, str], dict[str, str]]] = {}
    for raw_id, entry in raw.items():
        if not isinstance(raw_id, str) or not isinstance(entry, dict):
            continue
        signature = entry.get("signature")
        tag_hints = entry.get("tags")
        if not isinstance(signature, dict) or not isinstance(tag_hints, dict):
            continue
        try:
            node_id = int(raw_id)
        except ValueError:
            continue
        result[node_id] = (
            {str(key): str(value) for key, value in signature.items()},
            {
                str(key): str(value)
                for key, value in tag_hints.items()
                if str(key) in _CONTEXT_TAGS
            },
        )
    return result


def _apply_poi_hint(
    node_id: int,
    tags: dict[str, str],
    poi_hints: dict[int, tuple[dict[str, str], dict[str, str]]],
    counters: Counter[str],
) -> dict[str, str]:
    hint = poi_hints.get(node_id)
    if hint is None:
        return tags
    expected_signature, tag_hints = hint
    if _signature(tags) != expected_signature:
        counters["poi_stale_skipped"] += 1
        return tags
    changed = False
    for key, value in tag_hints.items():
        if tags.get(key) != value:
            tags[key] = value
            changed = True
    if changed:
        counters["poi_tagged"] += 1
    return tags


def _write_synthetic_area_poi(
    writer: Any,
    osmium: Any,
    candidate: SyntheticAreaPoi,
    poi_hints: dict[int, tuple[dict[str, str], dict[str, str]]],
    counters: Counter[str],
    semantic_transformer: Any,
) -> None:
    node = osmium.osm.mutable.Node(
        id=candidate.synthetic_id,
        location=(candidate.lon, candidate.lat),
        tags=candidate.tags,
    )
    tags = dict(candidate.tags)
    if semantic_transformer is not None:
        tags = semantic_transformer.transform(node, tags)
    tags = _apply_poi_hint(candidate.synthetic_id, tags, poi_hints, counters)
    writer.add_node(
        osmium.osm.mutable.Node(
            id=candidate.synthetic_id,
            location=(candidate.lon, candidate.lat),
            tags=tags,
        )
    )
    counters["synthetic_area_pois"] += 1


def _validated_area_enrichments(
    source: Path,
    enrichments: Sequence[AreaPoiEnrichment],
    osmium: Any,
    counters: Counter[str],
) -> dict[int, list[AreaPoiEnrichment]]:
    """Validate both cached objects before changing an existing real node."""
    if not enrichments:
        return {}
    wanted_nodes = {entry.node_id for entry in enrichments}
    wanted_ways = {entry.source_id for entry in enrichments}
    node_versions: dict[int, int | None] = {}
    way_versions: dict[int, int | None] = {}
    for item in osmium.FileProcessor(str(source)):
        kind = getattr(item, "type_str", lambda: "")()
        item_id = int(item.id)
        if kind in {"n", "node"}:
            target, wanted = node_versions, wanted_nodes
        elif kind in {"w", "way"}:
            target, wanted = way_versions, wanted_ways
        else:
            continue
        if item_id not in wanted:
            continue
        try:
            target[item_id] = int(item.version)
        except (AttributeError, TypeError, ValueError):
            target[item_id] = None
        if len(node_versions) == len(wanted_nodes) and len(way_versions) == len(wanted_ways):
            break

    result: dict[int, list[AreaPoiEnrichment]] = {}
    for entry in enrichments:
        valid = (
            entry.node_version is not None
            and entry.source_version is not None
            and node_versions.get(entry.node_id) == entry.node_version
            and way_versions.get(entry.source_id) == entry.source_version
        )
        if valid:
            result.setdefault(entry.node_id, []).append(entry)
        else:
            counters["area_enrichment_stale_skipped"] += 1
    return result


def apply_analysis_bundle(
    input_path: str | Path,
    analysis_dir: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
    semantic_transformer: Any = None,
    synthetic_area_pois: Sequence[SyntheticAreaPoi] = (),
    reusable_area_entries: Sequence[tuple[SyntheticAreaPoi, int | None]] = (),
    reusable_area_enrichments: Sequence[AreaPoiEnrichment] = (),
) -> dict[str, int]:
    """Apply cheap semantics first, then compatible cached hints, in one writer pass.

    ``reusable_area_entries`` are injected only when the corresponding source way
    still exists with the exact OSM version recorded during ANALYZE.  This lets the
    cache survive a newer Geofabrik extract while conservatively skipping edited or
    deleted source polygons.
    """
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    root = Path(analysis_dir).resolve()
    if source == target:
        raise StageError("analysis apply input and output must be different files")
    road_hints = _load_road_hints(root / "road-density.json.gz")
    poi_hints = _load_poi_hints(root / "poi-context.json.gz")
    reusable_by_way: dict[int, tuple[SyntheticAreaPoi, int | None]] = {
        candidate.source_id: (candidate, source_version)
        for candidate, source_version in reusable_area_entries
    }
    pending_reusable = set(reusable_by_way)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.bundle-apply.partial.osm.pbf"
    counters: Counter[str] = Counter()
    valid_area_enrichments = _validated_area_enrichments(
        source, reusable_area_enrichments, osmium, counters
    )
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            # Current-source candidates (cache-building path) are already known to be
            # valid.  Reuse candidates are deferred until their source way is seen.
            for candidate in synthetic_area_pois:
                _write_synthetic_area_poi(
                    writer, osmium, candidate, poi_hints, counters, semantic_transformer
                )

            for item in osmium.FileProcessor(str(source)):
                counters["objects_seen"] += 1
                type_method = getattr(item, "type_str", None)
                kind = type_method() if callable(type_method) else ""
                item_id = int(item.id)
                original_tags = {str(key): str(value) for key, value in item.tags}
                tags = dict(original_tags)

                if kind in {"node", "n"} and item_id in valid_area_enrichments:
                    changed = False
                    for enrichment in valid_area_enrichments[item_id]:
                        counters["area_enrichment_matches"] += 1
                        added: list[str] = []
                        for key, value in enrichment.added_tags.items():
                            if key not in tags:
                                tags[key] = value
                                added.append(key)
                                changed = True
                        if reporter is not None and added:
                            reporter(
                                f"area POI merge {enrichment.family}: "
                                f"node{enrichment.node_id} {enrichment.node_kind} <- "
                                f"way{enrichment.source_id} {enrichment.area_kind}; "
                                f"added={','.join(sorted(added))}"
                            )
                    if changed:
                        counters["area_enriched_nodes"] += 1

                # When reusing area artifacts, validate the source way before
                # recreating its synthetic node.  OSM version changes on geometry or
                # tag edits, so a mismatch is a strong cheap stale signal.
                if kind in {"way", "w"} and item_id in reusable_by_way:
                    candidate, expected_version = reusable_by_way[item_id]
                    pending_reusable.discard(item_id)
                    try:
                        current_version = int(item.version)
                    except (AttributeError, TypeError, ValueError):
                        current_version = None
                    if expected_version is not None and current_version == expected_version:
                        _write_synthetic_area_poi(
                            writer,
                            osmium,
                            candidate,
                            poi_hints,
                            counters,
                            semantic_transformer,
                        )
                    else:
                        counters["area_stale_skipped"] += 1

                # Production preprocess performs blacklist/cheap semantic transforms
                # before both POI-context and road-density calculations. Do the same
                # here so freshness guards compare like with like.
                if semantic_transformer is not None:
                    tags = semantic_transformer.transform(item, tags)

                if kind in {"node", "n"}:
                    tags = _apply_poi_hint(item_id, tags, poi_hints, counters)
                elif kind in {"way", "w"}:
                    hint = road_hints.get(item_id)
                    if hint is not None:
                        expected_class, level = hint
                        if road_density_class(tags) == expected_class and tags.get("area") != "yes":
                            changed = False
                            if tags.get(ROAD_DENSITY_TAG) != level:
                                tags[ROAD_DENSITY_TAG] = level
                                changed = True
                            if tags.get(ROAD_DENSITY_CLASS_TAG) != expected_class:
                                tags[ROAD_DENSITY_CLASS_TAG] = expected_class
                                changed = True
                            if changed:
                                counters["road_tagged"] += 1
                        else:
                            counters["road_stale_skipped"] += 1

                writer.add(item if tags == original_tags else item.replace(tags=tags))
        counters["area_missing_skipped"] = len(pending_reusable)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    result = {
        "objects_seen": counters["objects_seen"],
        "synthetic_area_pois": counters["synthetic_area_pois"],
        "area_stale_skipped": counters["area_stale_skipped"],
        "area_missing_skipped": counters["area_missing_skipped"],
        "area_enrichment_matches": counters["area_enrichment_matches"],
        "area_enriched_nodes": counters["area_enriched_nodes"],
        "area_enrichment_stale_skipped": counters["area_enrichment_stale_skipped"],
        "road_hints": len(road_hints),
        "road_tagged": counters["road_tagged"],
        "road_stale_skipped": counters["road_stale_skipped"],
        "poi_hints": len(poi_hints),
        "poi_tagged": counters["poi_tagged"],
        "poi_stale_skipped": counters["poi_stale_skipped"],
    }
    if reporter is not None:
        reporter(
            "Analysis bundle applied: "
            f"area POI {result['synthetic_area_pois']:,}; "
            f"area stale={result['area_stale_skipped']:,} missing={result['area_missing_skipped']:,}; "
            f"area merge={result['area_enriched_nodes']:,}/{result['area_enrichment_matches']:,} "
            f"stale={result['area_enrichment_stale_skipped']:,}; "
            f"road {result['road_tagged']:,}/{result['road_hints']:,}; "
            f"POI {result['poi_tagged']:,}/{result['poi_hints']:,}; "
            f"stale road={result['road_stale_skipped']:,} poi={result['poi_stale_skipped']:,}"
        )
    return result

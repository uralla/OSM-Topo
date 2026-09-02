"""Parallel reusable analysis bundle and one-pass application to fresh OSM."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

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


def apply_analysis_bundle(
    input_path: str | Path,
    analysis_dir: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
    semantic_transformer: Any = None,
) -> dict[str, int]:
    """Apply reusable artifacts and optional cheap semantics in one PBF writer pass."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    root = Path(analysis_dir).resolve()
    if source == target:
        raise StageError("analysis apply input and output must be different files")
    road_hints = _load_road_hints(root / "road-density.json.gz")
    poi_hints = _load_poi_hints(root / "poi-context.json.gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.bundle-apply.partial.osm.pbf"
    counters: Counter[str] = Counter()
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)):
                counters["objects_seen"] += 1
                type_method = getattr(item, "type_str", None)
                kind = type_method() if callable(type_method) else ""
                original_tags = {str(key): str(value) for key, value in item.tags}
                tags = dict(original_tags)
                analysis_changed = False
                if kind == "node":
                    hint = poi_hints.get(int(item.id))
                    if hint is not None:
                        expected_signature, tag_hints = hint
                        if _signature(tags) == expected_signature:
                            for key, value in tag_hints.items():
                                if tags.get(key) != value:
                                    tags[key] = value
                                    analysis_changed = True
                            if analysis_changed:
                                counters["poi_tagged"] += 1
                        else:
                            counters["poi_stale_skipped"] += 1
                elif kind == "way":
                    hint = road_hints.get(int(item.id))
                    if hint is not None:
                        expected_class, level = hint
                        if road_density_class(tags) == expected_class and tags.get("area") != "yes":
                            if tags.get(ROAD_DENSITY_TAG) != level:
                                tags[ROAD_DENSITY_TAG] = level
                                analysis_changed = True
                            if tags.get(ROAD_DENSITY_CLASS_TAG) != expected_class:
                                tags[ROAD_DENSITY_CLASS_TAG] = expected_class
                                analysis_changed = True
                            if analysis_changed:
                                counters["road_tagged"] += 1
                        else:
                            counters["road_stale_skipped"] += 1

                if semantic_transformer is not None:
                    tags = semantic_transformer.transform(item, tags)

                writer.add(item if tags == original_tags else item.replace(tags=tags))
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    result = {
        "objects_seen": counters["objects_seen"],
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
            f"road {result['road_tagged']:,}/{result['road_hints']:,}; "
            f"POI {result['poi_tagged']:,}/{result['poi_hints']:,}; "
            f"stale road={result['road_stale_skipped']:,} poi={result['poi_stale_skipped']:,}"
        )
    return result

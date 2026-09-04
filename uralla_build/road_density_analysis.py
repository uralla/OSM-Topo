"""Reusable road-density analysis artifact for analyze/apply preprocessing."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .errors import StageError
from .road_density import (
    CELL_DEGREES,
    ROAD_DENSITY_CLASS_TAG,
    ROAD_DENSITY_TAG,
    SEGMENT_SAMPLE_METRES,
    THRESHOLDS,
    WAY_DENSE_SHARE,
    _build_density_index,
    _tags_dict,
    _way_cell_lengths,
    _way_level,
    _way_points,
    road_density_class,
)

# v2 changed density class semantics from broad local/track/trail families to
# concrete same-class road networks. v3 adds a deterministic representative
# "keep" hint for each connected dense cluster, so decluttering cannot erase
# an entire same-class branch from far zooms.
SCHEMA_VERSION = 3
ANALYSIS_KIND = "road_density"
_VALID_LEVELS = frozenset({"dense", "very_dense", "keep"})


def _parameters() -> dict[str, object]:
    return {
        "cell_degrees": CELL_DEGREES,
        "segment_sample_metres": SEGMENT_SAMPLE_METRES,
        "way_dense_share": WAY_DENSE_SHARE,
        "representative_keep": "one per connected dense same-class cell cluster",
        "thresholds": {
            name: {
                "dense_km_per_km2": value.dense_km_per_km2,
                "very_dense_km_per_km2": value.very_dense_km_per_km2,
            }
            for name, value in THRESHOLDS.items()
        },
    }


def save_road_density_analysis(path: str | Path, payload: dict[str, object]) -> None:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.partial"
    try:
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_road_density_analysis(path: str | Path) -> dict[str, object]:
    source = Path(path).resolve()
    try:
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StageError(f"cannot load road-density analysis {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StageError("road-density analysis root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != ANALYSIS_KIND:
        raise StageError(f"unsupported road-density analysis artifact: {source}")
    if not isinstance(payload.get("ways"), dict):
        raise StageError("road-density analysis ways must be an object")
    return payload


def _dense_components(
    levels: Mapping[tuple[str, int, int], str],
) -> dict[tuple[str, int, int], int]:
    """Label 8-neighbour connected dense cells independently per road class."""

    pending = set(levels)
    result: dict[tuple[str, int, int], int] = {}
    component_id = 0
    while pending:
        start = min(pending)
        pending.remove(start)
        render_class, start_x, start_y = start
        stack = [(start_x, start_y)]
        result[start] = component_id
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    key = (render_class, x + dx, y + dy)
                    if key not in pending:
                        continue
                    pending.remove(key)
                    result[key] = component_id
                    stack.append((x + dx, y + dy))
        component_id += 1
    return result


def _representative_keep_ids(
    source: Path,
    osmium: Any,
    levels: Mapping[tuple[str, int, int], str],
) -> tuple[dict[int, tuple[str, str]], set[int], Counter[tuple[str, str]]]:
    """Classify dense ways and keep one deterministic stem per dense cluster."""

    components = _dense_components(levels)
    raw: dict[int, tuple[str, str]] = {}
    tagged: Counter[tuple[str, str]] = Counter()
    # (class, component) -> (rank, way_id). Rank prefers the greatest length
    # inside the component, then a named road, then total length, then lower OSM id.
    best: dict[tuple[str, int], tuple[tuple[float, int, float, int], int]] = {}

    for item in osmium.FileProcessor(str(source)).with_locations():
        tags = _tags_dict(item.tags)
        render_class = road_density_class(tags)
        if render_class is None or tags.get("area") == "yes":
            continue
        points = _way_points(item)
        if len(points) < 2:
            continue
        level, _dense_share, _very_dense_share = _way_level(render_class, points, levels)
        if level is None:
            continue

        way_id = int(item.id)
        raw[way_id] = (render_class, level)
        cell_lengths = _way_cell_lengths(points)
        total_metres = sum(cell_lengths.values())
        by_component: dict[int, float] = defaultdict(float)
        for (x, y), metres in cell_lengths.items():
            component_id = components.get((render_class, x, y))
            if component_id is not None:
                by_component[component_id] += metres

        named = 1 if bool(tags.get("name")) else 0
        for component_id, overlap_metres in by_component.items():
            rank = (overlap_metres, named, total_metres, -way_id)
            key = (render_class, component_id)
            current = best.get(key)
            if current is None or rank > current[0]:
                best[key] = (rank, way_id)

    keep_ids = {way_id for _rank, way_id in best.values()}
    for way_id, (render_class, level) in raw.items():
        final_level = "keep" if way_id in keep_ids else level
        raw[way_id] = (render_class, final_level)
        tagged[(render_class, final_level)] += 1
    return raw, keep_ids, tagged


def analyze_road_density(
    input_path: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
) -> dict[str, object]:
    """Run expensive spatial analysis and persist reusable per-way hints."""

    source = Path(input_path).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"road-density input is missing or empty: {source}")

    levels, stats = _build_density_index(source, osmium)
    classified, keep_ids, tagged = _representative_keep_ids(source, osmium, levels)
    ways = {
        str(way_id): [render_class, level]
        for way_id, (render_class, level) in classified.items()
    }

    stats["tagged_ways"] = len(ways)
    stats["kept_ways"] = len(keep_ids)
    stats["tagged_by_class"] = {
        render_class: {
            "dense": tagged[(render_class, "dense")],
            "very_dense": tagged[(render_class, "very_dense")],
            "keep": tagged[(render_class, "keep")],
        }
        for render_class in THRESHOLDS
    }
    stat = source.stat()
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"path": str(source), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        "parameters": _parameters(),
        "stats": stats,
        "ways": ways,
    }
    save_road_density_analysis(output_path, payload)
    if reporter is not None:
        reporter(
            f"Road-density analysis saved; hints {len(ways):,}; "
            f"representative keeps {len(keep_ids):,}"
        )
    return stats


def apply_road_density_analysis(
    input_path: str | Path,
    analysis_path: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
) -> dict[str, int]:
    """Apply cached hints to a fresh PBF in one cheap non-spatial pass."""

    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    if source == target:
        raise StageError("road-density apply input and output must be different files")
    payload = load_road_density_analysis(analysis_path)
    raw_ways = payload["ways"]
    assert isinstance(raw_ways, dict)
    hints: dict[int, tuple[str, str]] = {}
    for raw_id, raw_hint in raw_ways.items():
        if not isinstance(raw_id, str) or not isinstance(raw_hint, list) or len(raw_hint) != 2:
            continue
        if raw_hint[0] not in THRESHOLDS or raw_hint[1] not in _VALID_LEVELS:
            continue
        try:
            hints[int(raw_id)] = (str(raw_hint[0]), str(raw_hint[1]))
        except ValueError:
            continue

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.analysis-apply.partial.osm.pbf"
    counters: Counter[str] = Counter()
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)):
                counters["objects_seen"] += 1
                type_method = getattr(item, "type_str", None)
                if not callable(type_method) or type_method() != "way":
                    writer.add(item)
                    continue
                hint = hints.get(int(item.id))
                if hint is None:
                    writer.add(item)
                    continue
                expected_class, level = hint
                tags = _tags_dict(item.tags)
                if road_density_class(tags) != expected_class or tags.get("area") == "yes":
                    counters["stale_skipped"] += 1
                    writer.add(item)
                    continue
                tags[ROAD_DENSITY_TAG] = level
                tags[ROAD_DENSITY_CLASS_TAG] = expected_class
                writer.add(item.replace(tags=tags))
                counters["tagged_ways"] += 1
                if level == "keep":
                    counters["kept_ways"] += 1
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    result = {
        "objects_seen": counters["objects_seen"],
        "tagged_ways": counters["tagged_ways"],
        "kept_ways": counters["kept_ways"],
        "stale_skipped": counters["stale_skipped"],
        "analysis_hints": len(hints),
    }
    if reporter is not None:
        reporter(
            f"Road-density analysis applied: hints {len(hints):,}; "
            f"tagged {result['tagged_ways']:,}; keeps {result['kept_ways']:,}; "
            f"stale skipped {result['stale_skipped']:,}"
        )
    return result

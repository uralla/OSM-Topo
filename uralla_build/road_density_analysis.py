"""Reusable road-density analysis artifact for analyze/apply preprocessing."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import json
import math
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
# concrete same-class road networks. v3 added one deterministic representative
# keep per connected dense cluster. v4 kept up to three connected ways. v5
# followed only unambiguous endpoint continuations and therefore could leave a
# visible trunk hanging at an ordinary junction. v6 chooses one natural
# continuation through a branch (ref/name first, then straightness) and allows
# that visual trunk to cross between eligible low road classes while density
# itself remains calculated independently per concrete class.
SCHEMA_VERSION = 6
ANALYSIS_KIND = "road_density"
_VALID_LEVELS = frozenset({"dense", "very_dense", "keep"})


@dataclass(frozen=True, slots=True)
class _Endpoint:
    node_ref: int
    # Unit vector from the endpoint into this way. At a junction the incoming
    # travel direction is therefore the negative of this vector.
    inward_x: float
    inward_y: float


@dataclass(frozen=True, slots=True)
class _BackboneCandidate:
    way_id: int
    render_class: str
    name: str
    ref: str
    rank: tuple[float, int, float, int]
    endpoints: tuple[_Endpoint, ...]


def _parameters() -> dict[str, object]:
    return {
        "cell_degrees": CELL_DEGREES,
        "segment_sample_metres": SEGMENT_SAMPLE_METRES,
        "way_dense_share": WAY_DENSE_SHARE,
        "representative_keep": (
            "endpoint-connected trunk from best per-class component seed; "
            "at branches prefer same ref/name then straightest continuation; "
            "continuation may cross eligible low road classes"
        ),
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


def _unit_vector(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return 0.0, 0.0
    return dx / length, dy / length


def _way_endpoints(item: object, points: list[tuple[float, float]]) -> tuple[_Endpoint, ...]:
    """Return endpoint refs plus local direction vectors for branch selection."""

    nodes = getattr(item, "nodes", None)
    if nodes is None or len(points) < 2:
        return ()
    try:
        refs = [int(node_ref.ref) for node_ref in nodes if getattr(node_ref, "ref", None) is not None]
    except (TypeError, ValueError):
        return ()
    if len(refs) != len(points) or not refs:
        return ()

    start_dx = points[1][0] - points[0][0]
    start_dy = points[1][1] - points[0][1]
    end_dx = points[-2][0] - points[-1][0]
    end_dy = points[-2][1] - points[-1][1]
    sx, sy = _unit_vector(start_dx, start_dy)
    ex, ey = _unit_vector(end_dx, end_dy)
    if refs[0] == refs[-1]:
        return (_Endpoint(refs[0], sx, sy),)
    return (_Endpoint(refs[0], sx, sy), _Endpoint(refs[-1], ex, ey))


def _endpoint_for(candidate: _BackboneCandidate, node_ref: int) -> _Endpoint | None:
    for endpoint in candidate.endpoints:
        if endpoint.node_ref == node_ref:
            return endpoint
    return None


def _continuation_score(
    current: _BackboneCandidate,
    node_ref: int,
    candidate: _BackboneCandidate,
) -> tuple[int, int, float, tuple[float, int, float, int]]:
    """Rank a branch continuation by identity, then geometric straightness."""

    same_ref = int(bool(current.ref) and current.ref == candidate.ref)
    same_name = int(bool(current.name) and current.name == candidate.name)
    current_endpoint = _endpoint_for(current, node_ref)
    candidate_endpoint = _endpoint_for(candidate, node_ref)
    straightness = -2.0
    if current_endpoint is not None and candidate_endpoint is not None:
        # Current inward vector points away from the junction along the way, so
        # negate it to obtain travel direction into the junction. Candidate
        # inward vector points from the junction into the candidate way.
        incoming_x = -current_endpoint.inward_x
        incoming_y = -current_endpoint.inward_y
        straightness = (
            incoming_x * candidate_endpoint.inward_x
            + incoming_y * candidate_endpoint.inward_y
        )
    return same_ref, same_name, straightness, candidate.rank


def _select_connected_backbone(
    candidates: Mapping[int, _BackboneCandidate],
    seed_id: int,
) -> set[int]:
    """Follow one deterministic natural trunk through endpoint junctions.

    Unlike v5, a junction no longer terminates the visible overview road. When
    several eligible continuations exist, keep exactly one: matching ref/name
    wins first, otherwise the geometrically straightest continuation wins.
    This keeps a coherent road skeleton without restoring every side branch.
    """

    seed = candidates.get(seed_id)
    if seed is None:
        return set()

    keep_ids = {seed_id}
    by_node: dict[int, list[int]] = defaultdict(list)
    for candidate in candidates.values():
        for endpoint in candidate.endpoints:
            by_node[endpoint.node_ref].append(candidate.way_id)

    frontier = deque((seed_id, endpoint.node_ref) for endpoint in seed.endpoints)
    visited: set[tuple[int, int]] = set()
    while frontier:
        current_id, node_ref = frontier.popleft()
        state = (current_id, node_ref)
        if state in visited:
            continue
        visited.add(state)
        current = candidates[current_id]

        alternatives = [
            candidates[way_id]
            for way_id in by_node.get(node_ref, ())
            if way_id != current_id and way_id not in keep_ids
        ]
        if not alternatives:
            continue

        chosen = max(
            alternatives,
            key=lambda candidate: _continuation_score(current, node_ref, candidate),
        )
        keep_ids.add(chosen.way_id)
        for endpoint in chosen.endpoints:
            if endpoint.node_ref != node_ref:
                frontier.append((chosen.way_id, endpoint.node_ref))

    return keep_ids


def _representative_keep_ids(
    source: Path,
    osmium: Any,
    levels: Mapping[tuple[str, int, int], str],
) -> tuple[dict[int, tuple[str, str]], set[int], Counter[tuple[str, str]]]:
    """Classify dense ways and retain one natural road trunk per dense cluster."""

    components = _dense_components(levels)
    raw: dict[int, tuple[str, str]] = {}
    tagged: Counter[tuple[str, str]] = Counter()
    # Density components remain per concrete class, but the topology candidate
    # pool is global across eligible low classes so a physical road does not
    # disappear merely because OSM changes highway=track to unclassified etc.
    seed_candidates: dict[
        tuple[str, int], list[tuple[tuple[float, int, float, int], int]]
    ] = defaultdict(list)
    topology_candidates: dict[int, _BackboneCandidate] = {}

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
        rank = (total_metres, named, total_metres, -way_id)
        topology_candidates[way_id] = _BackboneCandidate(
            way_id=way_id,
            render_class=render_class,
            name=str(tags.get("name") or ""),
            ref=str(tags.get("ref") or ""),
            rank=rank,
            endpoints=_way_endpoints(item, points),
        )
        for component_id, overlap_metres in by_component.items():
            component_rank = (overlap_metres, named, total_metres, -way_id)
            seed_candidates[(render_class, component_id)].append((component_rank, way_id))

    keep_ids: set[int] = set()
    for component_key in sorted(seed_candidates):
        component_candidates = seed_candidates[component_key]
        seed_id = max(component_candidates, key=lambda candidate: candidate[0])[1]
        keep_ids.update(_select_connected_backbone(topology_candidates, seed_id))

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
            f"backbone keeps {len(keep_ids):,}"
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

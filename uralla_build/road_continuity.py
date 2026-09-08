"""Find short low-class road chains that bridge overview-class roads."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import heapq
import math
from typing import Mapping


ROAD_CONTINUITY_TAG = "uralla:road_continuity"
ROAD_CONTINUITY_MAX_METRES = 6000.0
ROAD_CONTINUITY_START_CLASSES = frozenset({"secondary", "tertiary"})
ROAD_CONTINUITY_BRIDGE_CLASSES = frozenset(
    {"minor", "unclassified", "residential"}
)
ROAD_CONTINUITY_TARGET_RESOLUTION = {
    "secondary": 18,
    "tertiary": 18,
    "unclassified": 19,
    "minor": 20,
}


@dataclass(frozen=True, slots=True)
class RoadContinuityHint:
    render_class: str
    resolution: int
    version: int | None


@dataclass(frozen=True, slots=True)
class _BridgeEdge:
    other: int
    way_id: int
    metres: float


def _valid_location(node_ref: object) -> tuple[float, float] | None:
    location = getattr(node_ref, "location", None)
    valid = getattr(location, "valid", None)
    if callable(valid) and not valid():
        return None
    try:
        return float(getattr(location, "lon")), float(getattr(location, "lat"))
    except (AttributeError, TypeError, ValueError):
        return None


def _haversine_metres(
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    radius = 6_371_008.8
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    d_lat = lat2_rad - lat1_rad
    d_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(d_lon / 2.0) ** 2
    )
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(value)))


def _way_data(
    item: object,
) -> tuple[int, int, float, int | None] | None:
    nodes = getattr(item, "nodes", None)
    if nodes is None:
        return None
    try:
        node_refs = list(nodes)
    except TypeError:
        return None
    if len(node_refs) < 2:
        return None

    refs: list[int] = []
    points: list[tuple[float, float]] = []
    for node_ref in node_refs:
        try:
            refs.append(int(node_ref.ref))
        except (AttributeError, TypeError, ValueError):
            return None
        point = _valid_location(node_ref)
        if point is None:
            return None
        points.append(point)

    if refs[0] == refs[-1]:
        return None

    metres = sum(
        _haversine_metres(a, b)
        for a, b in zip(points, points[1:])
    )
    if metres <= 0.0:
        return None

    try:
        version = int(getattr(item, "version"))
    except (AttributeError, TypeError, ValueError):
        version = None
    return refs[0], refs[-1], metres, version


class RoadContinuityBuilder:
    """Collect an endpoint graph and select short deterministic bridge paths."""

    def __init__(self) -> None:
        self._graph: dict[int, list[_BridgeEdge]] = defaultdict(list)
        self._anchors: dict[int, list[tuple[int, int]]] = defaultdict(list)
        self._starts: set[tuple[int, int]] = set()
        self._meta: dict[int, tuple[str, int | None]] = {}

    def add(self, item: object, tags: Mapping[str, str]) -> None:
        highway = tags.get("highway")
        if (
            highway not in ROAD_CONTINUITY_TARGET_RESOLUTION
            and highway not in ROAD_CONTINUITY_BRIDGE_CLASSES
        ):
            return
        if tags.get("area") == "yes":
            return

        data = _way_data(item)
        if data is None:
            return
        start, end, metres, version = data
        way_id = int(getattr(item, "id"))

        target_resolution = ROAD_CONTINUITY_TARGET_RESOLUTION.get(highway)
        if target_resolution is not None:
            self._anchors[start].append((way_id, target_resolution))
            self._anchors[end].append((way_id, target_resolution))

        if highway in ROAD_CONTINUITY_START_CLASSES:
            self._starts.add((start, way_id))
            self._starts.add((end, way_id))

        if highway in ROAD_CONTINUITY_BRIDGE_CLASSES:
            self._graph[start].append(_BridgeEdge(end, way_id, metres))
            self._graph[end].append(_BridgeEdge(start, way_id, metres))
            self._meta[way_id] = (highway, version)

    @staticmethod
    def _path(
        start: int,
        end: int,
        previous: Mapping[int, tuple[int, int]],
    ) -> tuple[int, ...]:
        ways: list[int] = []
        node = end
        while node != start:
            parent = previous.get(node)
            if parent is None:
                return ()
            node, way_id = parent
            ways.append(way_id)
        ways.reverse()
        return tuple(ways)

    def _nearest_target(
        self,
        start_node: int,
        start_way_id: int,
    ) -> tuple[tuple[int, ...], int, float] | None:
        best = {start_node: 0.0}
        previous: dict[int, tuple[int, int]] = {}
        queue: list[tuple[float, int]] = [(0.0, start_node)]

        while queue:
            distance, node = heapq.heappop(queue)
            if distance > best.get(node, float("inf")):
                continue

            if distance > 0.0 and node in self._anchors:
                path = self._path(start_node, node, previous)
                path_ids = set(path)
                targets = [
                    (resolution, way_id)
                    for way_id, resolution in self._anchors[node]
                    if way_id != start_way_id and way_id not in path_ids
                ]
                if path and targets:
                    resolution, _target_way = min(targets)
                    return path, resolution, distance

            for edge in self._graph.get(node, ()):
                new_distance = distance + edge.metres
                if new_distance > ROAD_CONTINUITY_MAX_METRES:
                    continue
                if new_distance >= best.get(edge.other, float("inf")):
                    continue
                best[edge.other] = new_distance
                previous[edge.other] = (node, edge.way_id)
                heapq.heappush(queue, (new_distance, edge.other))

        return None

    def finish(
        self,
    ) -> tuple[dict[int, RoadContinuityHint], dict[str, object]]:
        for edges in self._graph.values():
            edges.sort(key=lambda edge: (edge.other, edge.way_id))

        hints: dict[int, RoadContinuityHint] = {}
        paths_found = 0
        start_junctions = 0

        for start_node, start_way_id in sorted(self._starts):
            if start_node not in self._graph:
                continue
            start_junctions += 1
            result = self._nearest_target(start_node, start_way_id)
            if result is None:
                continue
            path, resolution, _distance = result
            paths_found += 1
            for way_id in path:
                meta = self._meta.get(way_id)
                if meta is None:
                    continue
                render_class, version = meta
                candidate = RoadContinuityHint(
                    render_class,
                    resolution,
                    version,
                )
                existing = hints.get(way_id)
                if existing is None or resolution < existing.resolution:
                    hints[way_id] = candidate

        stats: dict[str, object] = {
            "max_bridge_metres": ROAD_CONTINUITY_MAX_METRES,
            "candidate_ways": len(self._meta),
            "start_junctions": start_junctions,
            "paths_found": paths_found,
            "tagged_ways": len(hints),
            "by_resolution": {
                str(resolution): sum(
                    hint.resolution == resolution for hint in hints.values()
                )
                for resolution in (18, 19, 20)
            },
        }
        return hints, stats

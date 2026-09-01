"""Deliberate area-to-POI synthesis for selected semantic categories.

mkgmap's global add-pois-to-areas option stays disabled. This module creates only
explicitly allowed POIs, suppresses them when a real equivalent node already exists
inside the polygon, and chooses a point guaranteed to be inside a simple polygon.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4


SYNTHETIC_AREA_POI_TAG = "uralla:synthetic_area_poi"


@dataclass(frozen=True, slots=True)
class SyntheticAreaPoi:
    source_type: str
    source_id: int
    lon: float
    lat: float
    tags: dict[str, str]


def _point_on_segment(
    x: float,
    y: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    *,
    epsilon: float = 1e-12,
) -> bool:
    cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
    if abs(cross) > epsilon:
        return False
    return (
        min(ax, bx) - epsilon <= x <= max(ax, bx) + epsilon
        and min(ay, by) - epsilon <= y <= max(ay, by) + epsilon
    )


def point_in_polygon(point: tuple[float, float], ring: Sequence[tuple[float, float]]) -> bool:
    """Return True for points inside or on the boundary of a simple polygon."""
    if len(ring) < 4:
        return False
    x, y = point
    inside = False
    for index in range(len(ring) - 1):
        ax, ay = ring[index]
        bx, by = ring[index + 1]
        if _point_on_segment(x, y, ax, ay, bx, by):
            return True
        if (ay > y) == (by > y):
            continue
        intersection_x = ax + (y - ay) * (bx - ax) / (by - ay)
        if intersection_x > x:
            inside = not inside
    return inside


def interior_point(ring: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
    """Choose a point strictly inside a simple polygon when possible.

    Horizontal scanlines between vertex Y coordinates are intersected with the
    polygon and the midpoint of the widest inside interval is selected. Unlike a
    bounding-box or vertex centroid, this remains inside concave/L-shaped polygons.
    """
    if len(ring) < 4 or ring[0] != ring[-1]:
        return None
    xs = [point[0] for point in ring[:-1]]
    ys = [point[1] for point in ring[:-1]]
    if not xs or not ys:
        return None
    unique_y = sorted(set(ys))
    if len(unique_y) == 1:
        return None
    candidates = [
        (low + high) / 2.0
        for low, high in zip(unique_y, unique_y[1:])
        if high > low
    ]
    center_y = (min(ys) + max(ys)) / 2.0
    candidates.sort(key=lambda value: abs(value - center_y))
    best: tuple[float, float, float] | None = None
    for y in candidates:
        crossings: list[float] = []
        for index in range(len(ring) - 1):
            ax, ay = ring[index]
            bx, by = ring[index + 1]
            if (ay > y) == (by > y):
                continue
            crossings.append(ax + (y - ay) * (bx - ax) / (by - ay))
        crossings.sort()
        for left, right in zip(crossings[0::2], crossings[1::2]):
            width = right - left
            if width <= 0:
                continue
            x = (left + right) / 2.0
            if not point_in_polygon((x, y), ring):
                continue
            if best is None or width > best[0]:
                best = (width, x, y)
    if best is not None:
        return best[1], best[2]
    return None


def _tags_dict(tags: Mapping[str, str] | object) -> dict[str, str]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    return {str(key): str(value) for key, value in items}


def _is_marketplace(tags: Mapping[str, str]) -> bool:
    return tags.get("amenity") == "marketplace"


def discover_marketplace_area_pois(source: str, osmium: Any) -> list[SyntheticAreaPoi]:
    """Find marketplace polygons missing an equivalent real node inside them.

    Closed ways are supported deliberately. Multipolygon relation support can be
    added in this module without changing the preprocessor/style contract.
    """
    real_nodes: list[tuple[float, float]] = []
    areas: list[tuple[int, list[tuple[float, float]], dict[str, str]]] = []

    processor = osmium.FileProcessor(source).with_locations()
    for item in processor:
        tags = _tags_dict(item.tags)
        if not _is_marketplace(tags):
            continue
        location = getattr(item, "location", None)
        if location is not None:
            valid = getattr(location, "valid", None)
            if not callable(valid) or valid():
                try:
                    real_nodes.append((float(location.lon), float(location.lat)))
                    continue
                except (AttributeError, TypeError, ValueError):
                    pass

        nodes = getattr(item, "nodes", None)
        if nodes is None:
            continue
        ring: list[tuple[float, float]] = []
        try:
            for node_ref in nodes:
                node_location = node_ref.location
                valid = getattr(node_location, "valid", None)
                if callable(valid) and not valid():
                    ring = []
                    break
                ring.append((float(node_location.lon), float(node_location.lat)))
        except (AttributeError, TypeError, ValueError):
            continue
        if len(ring) < 4 or ring[0] != ring[-1]:
            continue
        areas.append((int(item.id), ring, tags))

    result: list[SyntheticAreaPoi] = []
    for source_id, ring, tags in areas:
        min_x = min(point[0] for point in ring)
        max_x = max(point[0] for point in ring)
        min_y = min(point[1] for point in ring)
        max_y = max(point[1] for point in ring)
        duplicate = any(
            min_x <= lon <= max_x
            and min_y <= lat <= max_y
            and point_in_polygon((lon, lat), ring)
            for lon, lat in real_nodes
        )
        if duplicate:
            continue
        point = interior_point(ring)
        if point is None:
            continue
        lon, lat = point
        synthetic_tags = dict(tags)
        synthetic_tags[SYNTHETIC_AREA_POI_TAG] = "yes"
        result.append(
            SyntheticAreaPoi(
                source_type="way",
                source_id=source_id,
                lon=lon,
                lat=lat,
                tags=synthetic_tags,
            )
        )
    return result


def augment_marketplace_area_pois(
    input_path: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
) -> dict[str, int]:
    """Copy a preprocessed PBF and prepend missing marketplace centre POIs."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    candidates = discover_marketplace_area_pois(str(source), osmium)
    if reporter is not None:
        reporter(f"Area POI: marketplace candidates to synthesize: {len(candidates):,}")

    temporary = target.parent / f".{target.name}.{uuid4().hex}.area-poi.partial.osm.pbf"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for index, candidate in enumerate(candidates, start=1):
                synthetic_id = -(9_000_000_000_000_000 + index)
                writer.add_node(
                    osmium.osm.mutable.Node(
                        id=synthetic_id,
                        location=(candidate.lon, candidate.lat),
                        tags=candidate.tags,
                    )
                )
                if reporter is not None:
                    reporter(
                        "[preprocess] area POI marketplace "
                        f"{candidate.source_type}{candidate.source_id}: "
                        f"{candidate.tags.get('name')!r} -> node{synthetic_id} "
                        f"({candidate.lat:.6f}, {candidate.lon:.6f})"
                    )
            for item in osmium.FileProcessor(str(source)):
                writer.add(item)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    return {
        "marketplace_candidates": len(candidates),
        "marketplace_created": len(candidates),
    }

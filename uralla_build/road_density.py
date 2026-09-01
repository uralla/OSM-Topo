"""Detect abnormally dense low-class road networks for far-zoom decluttering.

The analysis is deliberately cartographic rather than semantic: only highway
classes below tertiary participate, and nearby ways are grouped by the visual
family that can create a screen-density problem.  Nothing is removed and no
routing/access tag is changed.  Ways are only marked so the mkgmap style can
move their far overview representation inward by one or two resolutions.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


ROAD_DENSITY_TAG = "uralla:road_density"
ROAD_DENSITY_CLASS_TAG = "uralla:road_density_class"

# A 0.005-degree cell is roughly 0.56 km north/south.  Density is normalized by
# the actual cell area at its latitude, so the threshold remains useful from
# southern regions to northern Russia despite longitude convergence.
CELL_DEGREES = 0.005
SEGMENT_SAMPLE_METRES = 150.0
WAY_DENSE_SHARE = 0.55


@dataclass(frozen=True, slots=True)
class DensityThreshold:
    dense_km_per_km2: float
    very_dense_km_per_km2: float


# Absolute thresholds are intentional.  Percentiles would classify something
# as "dense" even in a generally sparse map extract.  These values correspond
# roughly to street grids with spacing of ~110 m (dense) and ~60 m
# (very_dense), with slightly lower thresholds for forestry tracks.
THRESHOLDS: dict[str, DensityThreshold] = {
    "local": DensityThreshold(18.0, 32.0),
    "track": DensityThreshold(14.0, 28.0),
    "trail": DensityThreshold(20.0, 36.0),
}

_LOCAL_HIGHWAYS = frozenset(
    {
        "minor",
        "unclassified",
        "residential",
        "living_street",
        "service",
        "road",
        "pedestrian",
    }
)
_TRACK_HIGHWAYS = frozenset({"track", "unsurfaced", "byway"})
_TRAIL_HIGHWAYS = frozenset({"path", "footway", "cycleway", "bridleway"})


def road_density_class(tags: Mapping[str, str]) -> str | None:
    """Return the low-road render family used for density accounting."""

    highway = tags.get("highway")
    if highway in _LOCAL_HIGHWAYS:
        return "local"
    if highway in _TRACK_HIGHWAYS:
        return "track"
    if highway in _TRAIL_HIGHWAYS:
        return "trail"
    return None


def _tags_dict(tags: Mapping[str, str] | object) -> dict[str, str]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    return {str(key): str(value) for key, value in items}


def _valid_location(location: object) -> tuple[float, float] | None:
    valid = getattr(location, "valid", None)
    if callable(valid) and not valid():
        return None
    try:
        return float(getattr(location, "lon")), float(getattr(location, "lat"))
    except (AttributeError, TypeError, ValueError):
        return None


def _way_points(item: object) -> list[tuple[float, float]]:
    nodes = getattr(item, "nodes", None)
    if nodes is None:
        return []
    result: list[tuple[float, float]] = []
    try:
        for node_ref in nodes:
            point = _valid_location(node_ref.location)
            if point is None:
                return []
            result.append(point)
    except (AttributeError, TypeError, ValueError):
        return []
    return result


def _haversine_metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    radius = 6_371_008.8
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    d_lat = lat2_rad - lat1_rad
    d_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2.0) ** 2
    )
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(value)))


def _cell(lon: float, lat: float) -> tuple[int, int]:
    return math.floor(lon / CELL_DEGREES), math.floor(lat / CELL_DEGREES)


def _cell_area_km2(cell: tuple[int, int]) -> float:
    _x, y = cell
    center_lat = (y + 0.5) * CELL_DEGREES
    north_south_km = 111.32 * CELL_DEGREES
    east_west_km = 111.32 * max(math.cos(math.radians(center_lat)), 0.05) * CELL_DEGREES
    return north_south_km * east_west_km


def _segment_samples(
    a: tuple[float, float], b: tuple[float, float]
) -> list[tuple[tuple[int, int], float]]:
    """Return grid cells crossed approximately by a segment and metres in each.

    Lower-class OSM ways are usually short, but long unclassified/track segments
    do occur.  Sampling at <=150 m prevents one long segment from being assigned
    wholesale to its midpoint cell without requiring a full line/grid clipper.
    """

    length = _haversine_metres(a, b)
    if length <= 0.0:
        return []
    parts = max(1, int(math.ceil(length / SEGMENT_SAMPLE_METRES)))
    piece = length / parts
    lon1, lat1 = a
    lon2, lat2 = b
    result: list[tuple[tuple[int, int], float]] = []
    for index in range(parts):
        fraction = (index + 0.5) / parts
        lon = lon1 + (lon2 - lon1) * fraction
        lat = lat1 + (lat2 - lat1) * fraction
        result.append((_cell(lon, lat), piece))
    return result


def _way_cell_lengths(points: list[tuple[float, float]]) -> dict[tuple[int, int], float]:
    result: dict[tuple[int, int], float] = defaultdict(float)
    for a, b in zip(points, points[1:]):
        for cell, metres in _segment_samples(a, b):
            result[cell] += metres
    return dict(result)


def _cell_level(render_class: str, density: float) -> str | None:
    threshold = THRESHOLDS[render_class]
    if density >= threshold.very_dense_km_per_km2:
        return "very_dense"
    if density >= threshold.dense_km_per_km2:
        return "dense"
    return None


def _build_density_index(
    source: Path, osmium: Any
) -> tuple[dict[tuple[str, int, int], str], dict[str, object]]:
    length_by_cell: dict[tuple[str, int, int], float] = defaultdict(float)
    eligible_ways = 0
    eligible_metres = 0.0

    for item in osmium.FileProcessor(str(source)).with_locations():
        tags = _tags_dict(item.tags)
        render_class = road_density_class(tags)
        if render_class is None or tags.get("area") == "yes":
            continue
        points = _way_points(item)
        if len(points) < 2:
            continue
        cell_lengths = _way_cell_lengths(points)
        if not cell_lengths:
            continue
        eligible_ways += 1
        way_metres = sum(cell_lengths.values())
        eligible_metres += way_metres
        for (x, y), metres in cell_lengths.items():
            length_by_cell[(render_class, x, y)] += metres

    levels: dict[tuple[str, int, int], str] = {}
    level_counts: Counter[tuple[str, str]] = Counter()
    for (render_class, x, y), metres in length_by_cell.items():
        area = _cell_area_km2((x, y))
        density = (metres / 1000.0) / area if area > 0 else 0.0
        level = _cell_level(render_class, density)
        if level is not None:
            levels[(render_class, x, y)] = level
            level_counts[(render_class, level)] += 1

    stats: dict[str, object] = {
        "eligible_ways": eligible_ways,
        "eligible_length_km": round(eligible_metres / 1000.0, 3),
        "occupied_cells": len(length_by_cell),
        "dense_cells": sum(level == "dense" for level in levels.values()),
        "very_dense_cells": sum(level == "very_dense" for level in levels.values()),
        "cells_by_class": {
            render_class: {
                "dense": level_counts[(render_class, "dense")],
                "very_dense": level_counts[(render_class, "very_dense")],
            }
            for render_class in THRESHOLDS
        },
    }
    return levels, stats


def _way_level(
    render_class: str,
    points: list[tuple[float, float]],
    levels: Mapping[tuple[str, int, int], str],
) -> tuple[str | None, float, float]:
    cell_lengths = _way_cell_lengths(points)
    total = sum(cell_lengths.values())
    if total <= 0.0:
        return None, 0.0, 0.0

    dense_metres = 0.0
    very_dense_metres = 0.0
    for (x, y), metres in cell_lengths.items():
        level = levels.get((render_class, x, y))
        if level in {"dense", "very_dense"}:
            dense_metres += metres
        if level == "very_dense":
            very_dense_metres += metres

    dense_share = dense_metres / total
    very_dense_share = very_dense_metres / total
    if very_dense_share >= WAY_DENSE_SHARE:
        return "very_dense", dense_share, very_dense_share
    if dense_share >= WAY_DENSE_SHARE:
        return "dense", dense_share, very_dense_share
    return None, dense_share, very_dense_share


def augment_road_density(
    input_path: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
) -> dict[str, object]:
    """Rewrite a PBF with density hints on low-class road ways."""

    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    levels, stats = _build_density_index(source, osmium)
    if reporter is not None:
        reporter(
            "Road density: "
            f"ways {stats['eligible_ways']:,}; "
            f"length {stats['eligible_length_km']:,.1f} km; "
            f"cells {stats['occupied_cells']:,}; "
            f"dense {stats['dense_cells']:,}; very_dense {stats['very_dense_cells']:,}"
        )
        for render_class, values in stats["cells_by_class"].items():  # type: ignore[union-attr]
            reporter(
                "Road density class: "
                f"{render_class}; dense={values['dense']:,}; "
                f"very_dense={values['very_dense']:,}"
            )

    temporary = target.parent / f".{target.name}.{uuid4().hex}.road-density.partial.osm.pbf"
    target.parent.mkdir(parents=True, exist_ok=True)
    tagged: Counter[tuple[str, str]] = Counter()
    samples: list[dict[str, object]] = []
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)).with_locations():
                tags = _tags_dict(item.tags)
                render_class = road_density_class(tags)
                if render_class is None or tags.get("area") == "yes":
                    writer.add(item)
                    continue
                points = _way_points(item)
                if len(points) < 2:
                    writer.add(item)
                    continue
                level, dense_share, very_dense_share = _way_level(
                    render_class, points, levels
                )
                if level is None:
                    writer.add(item)
                    continue
                tags[ROAD_DENSITY_TAG] = level
                tags[ROAD_DENSITY_CLASS_TAG] = render_class
                writer.add(item.replace(tags=tags))
                tagged[(render_class, level)] += 1
                if len(samples) < 24:
                    samples.append(
                        {
                            "id": int(item.id),
                            "highway": tags.get("highway"),
                            "name": tags.get("name"),
                            "class": render_class,
                            "level": level,
                            "dense_share": round(dense_share, 3),
                            "very_dense_share": round(very_dense_share, 3),
                        }
                    )
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    stats["tagged_ways"] = sum(tagged.values())
    stats["tagged_by_class"] = {
        render_class: {
            "dense": tagged[(render_class, "dense")],
            "very_dense": tagged[(render_class, "very_dense")],
        }
        for render_class in THRESHOLDS
    }
    stats["samples"] = samples
    if reporter is not None:
        reporter(f"Road density LOD: tagged ways {stats['tagged_ways']:,}")
        for sample in samples[:12]:
            reporter(
                "Road density sample: "
                f"way{sample['id']}; highway={sample['highway']}; "
                f"name={sample['name']!r}; class={sample['class']}; "
                f"level={sample['level']}; dense={float(sample['dense_share']) * 100:.0f}%; "
                f"very_dense={float(sample['very_dense_share']) * 100:.0f}%"
            )
    return stats

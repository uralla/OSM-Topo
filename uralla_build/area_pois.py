"""Deliberate area-to-POI synthesis for selected semantic categories.

mkgmap's global add-pois-to-areas option stays disabled. Only explicitly approved
closed ways become synthetic POIs. Multipolygon relations stay out of scope unless
a concrete important case requires them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .kite import is_kite_infrastructure


SYNTHETIC_AREA_POI_TAG = "uralla:synthetic_area_poi"
SYNTHETIC_AREA_POI_ID_BASE = 8_000_000_000_000_000


@dataclass(frozen=True, slots=True)
class SyntheticAreaPoi:
    source_type: str
    source_id: int
    kind: str
    lon: float
    lat: float
    tags: dict[str, str]

    @property
    def synthetic_id(self) -> int:
        return synthetic_area_poi_id(self.source_id)


def synthetic_area_poi_id(source_id: int) -> int:
    """Return a stable negative node ID for one source way.

    Area synthesis currently creates at most one POI per closed way, so the
    positive OSM way ID is a stable collision-free key within this reserved
    synthetic node range.
    """
    value = int(source_id)
    if value <= 0:
        raise ValueError(f"area POI source way ID must be positive, got {value}")
    return -(SYNTHETIC_AREA_POI_ID_BASE + value)


_AMENITY_AREA_POIS = frozenset(
    {
        "airport", "arts_centre", "bank", "bar", "bbq", "bicycle_rental",
        "bicycle_repair_station", "biergarten", "border_control", "bus_station",
        "car_rental", "car_sharing", "car_wash", "clinic", "college",
        "community_center", "community_centre", "convention_center", "courthouse",
        "dentist", "doctors", "embassy", "ferry_terminal", "fire_station",
        "firepit", "food_court", "fountain", "fuel", "grave_yard", "hospital",
        "library", "marketplace", "parking", "pharmacy", "place_of_worship",
        "police", "post_office", "prison", "pub", "public_building", "recycling",
        "restaurant", "cafe", "fast_food", "school", "shelter", "supermarket",
        "toilets", "townhall", "university", "waste_disposal", "zoo",
    }
)

_SHOP_AREA_POIS = frozenset(
    {
        "bakers", "bakery", "bicycle", "butcher", "car_parts", "car_rental",
        "car_repair", "car_wrecker", "convenience", "doityourself", "general",
        "grocery", "hardware", "houseware", "motorcycle", "organic", "outdoor",
        "outpost", "sports", "supermarket", "ticket",
    }
)

_TOURISM_AREA_POIS = frozenset(
    {
        "alpine_hut", "aquarium", "artwork", "attraction", "camp_site", "chalet",
        "guest_house", "hostel", "hotel", "information", "lean_to", "motel",
        "museum", "picnic_site", "theme_park", "viewpoint", "wilderness_hut",
        "wine_cellar", "zoo",
    }
)

_HISTORIC_AREA_POIS = frozenset(
    {"archaeological_site", "castle", "fort", "memorial", "monument", "museum", "ruins"}
)

_MAN_MADE_AREA_POIS = frozenset(
    {"antenna", "cairn", "communications_tower", "lighthouse", "mast", "survey_point", "tower", "water_tower", "windmill"}
)

_AEROWAY_AREA_POIS = frozenset({"aerodrome", "airport", "helipad", "terminal"})
_LANDUSE_AREA_POIS = frozenset({"basin", "cemetary", "cemetery", "quarry"})


def _point_on_segment(
    x: float, y: float, ax: float, ay: float, bx: float, by: float, *, epsilon: float = 1e-12,
) -> bool:
    cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
    if abs(cross) > epsilon:
        return False
    return min(ax, bx) - epsilon <= x <= max(ax, bx) + epsilon and min(ay, by) - epsilon <= y <= max(ay, by) + epsilon


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
    """Choose an inside point for a simple closed polygon, including concave ones."""
    if len(ring) < 4 or ring[0] != ring[-1]:
        return None
    ys = [point[1] for point in ring[:-1]]
    if not ys:
        return None
    unique_y = sorted(set(ys))
    if len(unique_y) == 1:
        return None
    candidates = [(low + high) / 2.0 for low, high in zip(unique_y, unique_y[1:]) if high > low]
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
            if point_in_polygon((x, y), ring) and (best is None or width > best[0]):
                best = (width, x, y)
    return None if best is None else (best[1], best[2])


def _tags_dict(tags: Mapping[str, str] | object) -> dict[str, str]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    return {str(key): str(value) for key, value in items}


def area_poi_kind(tags: Mapping[str, str]) -> str | None:
    """Return an approved synthetic-POI semantic kind for a closed way."""
    amenity = tags.get("amenity")
    if amenity in _AMENITY_AREA_POIS:
        return f"amenity:{amenity}"
    shop = tags.get("shop")
    if shop in _SHOP_AREA_POIS:
        return f"shop:{shop}"
    tourism = tags.get("tourism")
    if tourism in _TOURISM_AREA_POIS:
        return f"tourism:{tourism}"
    historic = tags.get("historic")
    if historic in _HISTORIC_AREA_POIS:
        return f"historic:{historic}"
    # Incomplete but common OSM tagging: a ruined building is still a useful
    # tourist POI even when historic=ruins is absent. Normalize only the
    # synthetic point, never the source polygon.
    if tags.get("building") == "ruins":
        return "historic:ruins"
    if tags.get("healthcare"):
        return f"healthcare:{tags['healthcare']}"
    man_made = tags.get("man_made")
    if man_made in _MAN_MADE_AREA_POIS:
        return f"man_made:{man_made}"
    if tags.get("landmark") == "chimney":
        return "landmark:chimney"
    aeroway = tags.get("aeroway")
    if aeroway in _AEROWAY_AREA_POIS:
        return f"aeroway:{aeroway}"
    landuse = tags.get("landuse")
    if landuse in _LANDUSE_AREA_POIS:
        if landuse == "basin" and not tags.get("name"):
            return None
        return f"landuse:{landuse}"
    if is_kite_infrastructure(tags):
        return "kite:infrastructure"
    if tags.get("office") == "government":
        return "office:government"
    if tags.get("military") == "bunker":
        return "military:bunker"
    if tags.get("craft") == "beekeeper":
        return "craft:beekeeper"
    if tags.get("railway") == "station":
        return "railway:station"
    return None


def discover_area_pois(source: str, osmium: Any) -> list[SyntheticAreaPoi]:
    """Find eligible closed ways missing a real equivalent POI node inside."""
    real_nodes: dict[str, list[tuple[float, float]]] = {}
    areas: list[tuple[int, str, list[tuple[float, float]], dict[str, str]]] = []
    for item in osmium.FileProcessor(source).with_locations():
        tags = _tags_dict(item.tags)
        kind = area_poi_kind(tags)
        if kind is None:
            continue
        location = getattr(item, "location", None)
        if location is not None:
            valid = getattr(location, "valid", None)
            if not callable(valid) or valid():
                try:
                    real_nodes.setdefault(kind, []).append((float(location.lon), float(location.lat)))
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
        areas.append((int(item.id), kind, ring, tags))
    result: list[SyntheticAreaPoi] = []
    for source_id, kind, ring, tags in areas:
        min_x = min(point[0] for point in ring)
        max_x = max(point[0] for point in ring)
        min_y = min(point[1] for point in ring)
        max_y = max(point[1] for point in ring)
        duplicate = any(
            min_x <= lon <= max_x and min_y <= lat <= max_y and point_in_polygon((lon, lat), ring)
            for lon, lat in real_nodes.get(kind, ())
        )
        if duplicate:
            continue
        point = interior_point(ring)
        if point is None:
            continue
        lon, lat = point
        synthetic_tags = dict(tags)
        if kind == "historic:ruins" and synthetic_tags.get("historic") != "ruins":
            synthetic_tags["historic"] = "ruins"
        synthetic_tags[SYNTHETIC_AREA_POI_TAG] = "yes"
        result.append(SyntheticAreaPoi("way", source_id, kind, lon, lat, synthetic_tags))
    result.sort(key=lambda candidate: candidate.source_id)
    return result


# Temporary compatibility for the older preprocessor import.
discover_marketplace_area_pois = discover_area_pois


def write_area_pois(
    input_path: str | Path,
    output_path: str | Path,
    candidates: Sequence[SyntheticAreaPoi],
    osmium: Any,
    *,
    reporter: Any = None,
) -> dict[str, int]:
    """Prepend already-discovered synthetic nodes and copy the source PBF."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    temporary = target.parent / f".{target.name}.{uuid4().hex}.area-poi.partial.osm.pbf"
    target.parent.mkdir(parents=True, exist_ok=True)
    created_by_kind: dict[str, int] = {}
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for candidate in candidates:
                synthetic_id = candidate.synthetic_id
                writer.add_node(osmium.osm.mutable.Node(id=synthetic_id, location=(candidate.lon, candidate.lat), tags=candidate.tags))
                created_by_kind[candidate.kind] = created_by_kind.get(candidate.kind, 0) + 1
                if reporter is not None:
                    reporter(
                        "area POI "
                        f"{candidate.kind} {candidate.source_type}{candidate.source_id}: "
                        f"{candidate.tags.get('name')!r} -> node{synthetic_id} "
                        f"({candidate.lat:.6f}, {candidate.lon:.6f})"
                    )
            for item in osmium.FileProcessor(str(source)):
                writer.add(item)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    stats: dict[str, int] = {"candidates": len(candidates), "created": len(candidates)}
    for kind, count in sorted(created_by_kind.items()):
        stats[f"created:{kind}"] = count
    return stats


def augment_area_pois(
    input_path: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
) -> dict[str, int]:
    """Discover, prepend, and copy approved missing area-derived POIs."""
    source = Path(input_path).resolve()
    candidates = discover_area_pois(str(source), osmium)
    if reporter is not None:
        reporter(f"Area POI: candidates to synthesize: {len(candidates):,}")
    return write_area_pois(source, output_path, candidates, osmium, reporter=reporter)

"""Deliberate area-to-POI synthesis for selected semantic categories.

mkgmap's global add-pois-to-areas option stays disabled. Only explicitly approved
closed ways become synthetic POIs. Multipolygon relations stay out of scope unless
a concrete important case requires them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
import unicodedata
from uuid import uuid4

from .kite import is_kite_infrastructure


SYNTHETIC_AREA_POI_TAG = "uralla:synthetic_area_poi"
SYNTHETIC_AREA_POI_ID_BASE = 8_000_000_000_000_000
AREA_POI_NEAR_DISTANCE_METRES = 8.0


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


@dataclass(frozen=True, slots=True)
class AreaPoiEnrichment:
    source_id: int
    source_version: int | None
    node_id: int
    node_version: int | None
    area_kind: str
    node_kind: str
    family: str
    match: str
    distance_metres: float
    added_tags: dict[str, str]


@dataclass(frozen=True, slots=True)
class AmbiguousAreaPoi:
    source_id: int
    kind: str
    family: str
    node_ids: tuple[int, ...]
    match: str


@dataclass(frozen=True, slots=True)
class AreaPoiPlan:
    synthetic: tuple[SyntheticAreaPoi, ...]
    enrichments: tuple[AreaPoiEnrichment, ...]
    ambiguous: tuple[AmbiguousAreaPoi, ...]


@dataclass(frozen=True, slots=True)
class _RealPoiNode:
    node_id: int
    version: int | None
    point: tuple[float, float]
    tags: dict[str, str]
    kinds: tuple[str, ...]


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
        "alpine_hut", "apartment", "aquarium", "artwork", "attraction", "camp_site", "chalet",
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

_ACCOMMODATION_VALUES = frozenset(
    {
        "alpine_hut", "apartment", "camp_site", "chalet", "guest_house", "hostel",
        "hotel", "lean_to", "motel", "wilderness_hut",
    }
)
_FOOD_VALUES = frozenset(
    {"bar", "biergarten", "cafe", "fast_food", "pub", "restaurant"}
)
_GEOMETRY_ONLY_KEYS = frozenset(
    {
        "area", "building", "building:levels", "building:min_level", "height",
        "min_height", "roof:colour", "roof:height", "roof:levels", "roof:material",
        "roof:orientation", "roof:shape", "type",
    }
)
_SPATIAL_CELL_DEGREES = 0.01


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


def _object_version(item: object) -> int | None:
    try:
        return int(getattr(item, "version"))
    except (AttributeError, TypeError, ValueError):
        return None


def _normalised_name(tags: Mapping[str, str]) -> str:
    value = unicodedata.normalize("NFKC", tags.get("name", "")).casefold()
    return " ".join(re.sub(r"[^0-9a-zа-яё]+", " ", value).split())


def _names_are_compatible(area_tags: Mapping[str, str], node_tags: Mapping[str, str]) -> bool:
    area_name = _normalised_name(area_tags)
    node_name = _normalised_name(node_tags)
    return not area_name or not node_name or area_name == node_name


def _merge_family(kind: str) -> str:
    prefix, _, value = kind.partition(":")
    if prefix == "tourism" and value in _ACCOMMODATION_VALUES:
        return "accommodation"
    if prefix == "shop" or kind == "amenity:supermarket":
        return "retail"
    if prefix == "amenity" and value in _FOOD_VALUES:
        return "food"
    if prefix in {"amenity", "healthcare"}:
        if value in {"clinic", "doctor", "doctors"}:
            return "medical:clinic_doctors"
        if value in {"pharmacy", "hospital", "dentist"}:
            return f"medical:{value}"
    return kind


def _copyable_area_tags(
    area_tags: Mapping[str, str], node_tags: Mapping[str, str], area_kind: str
) -> dict[str, str]:
    """Return useful missing tags without turning building geometry into node tags."""
    primary_key = area_kind.partition(":")[0]
    return {
        key: value
        for key, value in area_tags.items()
        if key not in node_tags
        and key != primary_key
        and key not in _GEOMETRY_ONLY_KEYS
        and not key.startswith(("building:", "roof:", "source:", "uralla:"))
        and key != "source"
    }


def _distance_to_segment_metres(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> float:
    lon, lat = point
    reference_lat = math.radians((lat + start[1] + end[1]) / 3.0)
    lon_scale = 111_320.0 * max(0.01, math.cos(reference_lat))
    lat_scale = 111_320.0
    px, py = lon * lon_scale, lat * lat_scale
    ax, ay = start[0] * lon_scale, start[1] * lat_scale
    bx, by = end[0] * lon_scale, end[1] * lat_scale
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    fraction = max(
        0.0,
        min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)),
    )
    return math.hypot(px - (ax + fraction * dx), py - (ay + fraction * dy))


def _distance_to_ring_metres(
    point: tuple[float, float], ring: Sequence[tuple[float, float]]
) -> float:
    return min(
        _distance_to_segment_metres(point, ring[index], ring[index + 1])
        for index in range(len(ring) - 1)
    )


def _cell(value: float) -> int:
    return math.floor(value / _SPATIAL_CELL_DEGREES)


def _nearby_nodes(
    index: Mapping[tuple[int, int], Sequence[_RealPoiNode]],
    ring: Sequence[tuple[float, float]],
) -> list[_RealPoiNode]:
    latitudes = [point[1] for point in ring]
    reference_lat = math.radians(max(abs(min(latitudes)), abs(max(latitudes))))
    lat_margin = AREA_POI_NEAR_DISTANCE_METRES / 111_320.0
    lon_margin = AREA_POI_NEAR_DISTANCE_METRES / (
        111_320.0 * max(0.01, math.cos(reference_lat))
    )
    min_x = min(point[0] for point in ring) - lon_margin
    max_x = max(point[0] for point in ring) + lon_margin
    min_y = min(latitudes) - lat_margin
    max_y = max(latitudes) + lat_margin
    result: dict[int, _RealPoiNode] = {}
    min_cell_x, max_cell_x = _cell(min_x), _cell(max_x)
    min_cell_y, max_cell_y = _cell(min_y), _cell(max_y)
    rectangle_cells = (max_cell_x - min_cell_x + 1) * (max_cell_y - min_cell_y + 1)
    if rectangle_cells <= max(1, len(index) * 4):
        cells = (
            (cell_x, cell_y)
            for cell_x in range(min_cell_x, max_cell_x + 1)
            for cell_y in range(min_cell_y, max_cell_y + 1)
        )
    else:
        cells = (
            (cell_x, cell_y)
            for cell_x, cell_y in index
            if min_cell_x <= cell_x <= max_cell_x
            and min_cell_y <= cell_y <= max_cell_y
        )
    for cell_key in cells:
        for node in index.get(cell_key, ()):
            result[node.node_id] = node
    return list(result.values())


def area_poi_equivalent_kinds(tags: Mapping[str, str]) -> tuple[str, ...]:
    """Return every approved semantic kind represented by one real POI.

    A real node may legitimately carry several independent OSM classifications,
    for example tourism=attraction + historic=castle.  Area synthesis chooses one
    primary kind, but duplicate suppression must see all equivalent kinds or it
    can create a second POI on top of the richer real node.
    """
    kinds: list[str] = []

    amenity = tags.get("amenity")
    if amenity in _AMENITY_AREA_POIS:
        kinds.append(f"amenity:{amenity}")

    shop = tags.get("shop")
    if shop in _SHOP_AREA_POIS:
        kinds.append(f"shop:{shop}")

    tourism = tags.get("tourism")
    if tourism in _TOURISM_AREA_POIS:
        kinds.append(f"tourism:{tourism}")

    historic = tags.get("historic")
    if historic in _HISTORIC_AREA_POIS:
        kinds.append(f"historic:{historic}")
    elif tags.get("building") == "ruins":
        kinds.append("historic:ruins")

    healthcare = tags.get("healthcare")
    if healthcare:
        kinds.append(f"healthcare:{healthcare}")

    man_made = tags.get("man_made")
    if man_made in _MAN_MADE_AREA_POIS:
        kinds.append(f"man_made:{man_made}")

    if tags.get("landmark") == "chimney":
        kinds.append("landmark:chimney")

    aeroway = tags.get("aeroway")
    if aeroway in _AEROWAY_AREA_POIS:
        kinds.append(f"aeroway:{aeroway}")

    landuse = tags.get("landuse")
    if landuse in _LANDUSE_AREA_POIS and not (landuse == "basin" and not tags.get("name")):
        kinds.append(f"landuse:{landuse}")

    if is_kite_infrastructure(tags):
        kinds.append("kite:infrastructure")
    if tags.get("office") == "government":
        kinds.append("office:government")
    if tags.get("military") == "bunker":
        kinds.append("military:bunker")
    if tags.get("craft") == "beekeeper":
        kinds.append("craft:beekeeper")
    if tags.get("railway") == "station":
        kinds.append("railway:station")

    return tuple(dict.fromkeys(kinds))


def area_poi_merge_families(tags: Mapping[str, str]) -> tuple[str, ...]:
    """Return conservative duplicate-matching families for a real POI node."""
    return tuple(
        dict.fromkeys(_merge_family(kind) for kind in area_poi_equivalent_kinds(tags))
    )


def area_poi_kind(tags: Mapping[str, str]) -> str | None:
    """Return the primary approved synthetic-POI semantic kind for a closed way."""
    kinds = area_poi_equivalent_kinds(tags)
    return kinds[0] if kinds else None


def discover_area_poi_plan(source: str, osmium: Any) -> AreaPoiPlan:
    """Plan synthetic POIs and safe area-to-existing-node enrichment."""
    real_nodes: dict[str, dict[tuple[int, int], list[_RealPoiNode]]] = defaultdict(
        lambda: defaultdict(list)
    )
    areas: list[
        tuple[int, int | None, str, list[tuple[float, float]], dict[str, str]]
    ] = []
    for item in osmium.FileProcessor(source).with_locations():
        tags = _tags_dict(item.tags)
        kinds = area_poi_equivalent_kinds(tags)
        if not kinds:
            continue
        kind = kinds[0]
        location = getattr(item, "location", None)
        if location is not None:
            valid = getattr(location, "valid", None)
            if not callable(valid) or valid():
                try:
                    point = (float(location.lon), float(location.lat))
                    node = _RealPoiNode(
                        node_id=int(item.id),
                        version=_object_version(item),
                        point=point,
                        tags=tags,
                        kinds=kinds,
                    )
                    for family in area_poi_merge_families(tags):
                        real_nodes[family][(_cell(point[0]), _cell(point[1]))].append(node)
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
        areas.append((int(item.id), _object_version(item), kind, ring, tags))

    synthetic: list[SyntheticAreaPoi] = []
    enrichments: list[AreaPoiEnrichment] = []
    ambiguous: list[AmbiguousAreaPoi] = []
    for source_id, source_version, kind, ring, tags in areas:
        family = _merge_family(kind)
        compatible = [
            node
            for node in _nearby_nodes(real_nodes.get(family, {}), ring)
            if _names_are_compatible(tags, node.tags)
        ]
        inside = [node for node in compatible if point_in_polygon(node.point, ring)]
        match = "inside"
        matches = inside
        distances = {node.node_id: 0.0 for node in inside}
        if not matches:
            match = "near"
            distances = {
                node.node_id: _distance_to_ring_metres(node.point, ring)
                for node in compatible
            }
            matches = [
                node
                for node in compatible
                if distances[node.node_id] <= AREA_POI_NEAR_DISTANCE_METRES
            ]

        if len(matches) > 1:
            ambiguous.append(
                AmbiguousAreaPoi(
                    source_id=source_id,
                    kind=kind,
                    family=family,
                    node_ids=tuple(sorted(node.node_id for node in matches)),
                    match=match,
                )
            )
            continue
        if len(matches) == 1:
            node = matches[0]
            node_kind = next(
                candidate_kind
                for candidate_kind in node.kinds
                if _merge_family(candidate_kind) == family
            )
            enrichments.append(
                AreaPoiEnrichment(
                    source_id=source_id,
                    source_version=source_version,
                    node_id=node.node_id,
                    node_version=node.version,
                    area_kind=kind,
                    node_kind=node_kind,
                    family=family,
                    match=match,
                    distance_metres=distances[node.node_id],
                    added_tags=_copyable_area_tags(tags, node.tags, kind),
                )
            )
            continue

        point = interior_point(ring)
        if point is None:
            continue
        lon, lat = point
        synthetic_tags = dict(tags)
        if kind == "historic:ruins" and synthetic_tags.get("historic") != "ruins":
            synthetic_tags["historic"] = "ruins"
        synthetic_tags[SYNTHETIC_AREA_POI_TAG] = "yes"
        synthetic.append(SyntheticAreaPoi("way", source_id, kind, lon, lat, synthetic_tags))
    synthetic.sort(key=lambda candidate: candidate.source_id)
    enrichments.sort(key=lambda entry: (entry.node_id, entry.source_id))
    ambiguous.sort(key=lambda entry: entry.source_id)
    return AreaPoiPlan(tuple(synthetic), tuple(enrichments), tuple(ambiguous))


def discover_area_pois(source: str, osmium: Any) -> list[SyntheticAreaPoi]:
    """Compatibility wrapper returning only synthetic-node candidates."""
    return list(discover_area_poi_plan(source, osmium).synthetic)


# Temporary compatibility for the older preprocessor import.
discover_marketplace_area_pois = discover_area_pois


def write_area_pois(
    input_path: str | Path,
    output_path: str | Path,
    candidates: Sequence[SyntheticAreaPoi],
    osmium: Any,
    *,
    reporter: Any = None,
    enrichments: Sequence[AreaPoiEnrichment] = (),
    ambiguous: Sequence[AmbiguousAreaPoi] = (),
) -> dict[str, int]:
    """Write synthetic nodes and enrich matched real nodes in one pass."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    temporary = target.parent / f".{target.name}.{uuid4().hex}.area-poi.partial.osm.pbf"
    target.parent.mkdir(parents=True, exist_ok=True)
    created_by_kind: dict[str, int] = {}
    enrichment_by_node: dict[int, list[AreaPoiEnrichment]] = defaultdict(list)
    for enrichment in enrichments:
        enrichment_by_node[enrichment.node_id].append(enrichment)
    enriched_nodes = 0
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
            for ambiguity in ambiguous:
                if reporter is not None:
                    reporter(
                        "area POI merge ambiguous: "
                        f"{ambiguity.kind} way{ambiguity.source_id}; "
                        f"family={ambiguity.family}; match={ambiguity.match}; "
                        f"nodes={','.join(str(node_id) for node_id in ambiguity.node_ids)}; "
                        "synthetic skipped"
                    )
            for item in osmium.FileProcessor(str(source)):
                item_enrichments = enrichment_by_node.get(int(item.id), ())
                if not item_enrichments or getattr(item, "type_str", lambda: "")() not in {"n", "node"}:
                    writer.add(item)
                    continue
                original_tags = _tags_dict(item.tags)
                tags = dict(original_tags)
                for enrichment in item_enrichments:
                    added_keys: list[str] = []
                    for key, value in enrichment.added_tags.items():
                        if key not in tags:
                            tags[key] = value
                            added_keys.append(key)
                    if reporter is not None:
                        added = ",".join(sorted(added_keys)) or "none"
                        distance = (
                            "inside"
                            if enrichment.match == "inside"
                            else f"near {enrichment.distance_metres:.1f}m"
                        )
                        reporter(
                            f"area POI merge {enrichment.family}: "
                            f"node{enrichment.node_id} {enrichment.node_kind} <- "
                            f"way{enrichment.source_id} {enrichment.area_kind}; "
                            f"match={distance}; added={added}"
                        )
                if tags != original_tags:
                    enriched_nodes += 1
                    writer.add(item.replace(tags=tags))
                else:
                    writer.add(item)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    stats: dict[str, int] = {
        "candidates": len(candidates),
        "created": len(candidates),
        "matched_areas": len(enrichments),
        "enriched_nodes": enriched_nodes,
        "ambiguous_areas": len(ambiguous),
        "near_matches": sum(entry.match == "near" for entry in enrichments),
    }
    for kind, count in sorted(created_by_kind.items()):
        stats[f"created:{kind}"] = count
    for enrichment in enrichments:
        key = f"matched:{enrichment.family}"
        stats[key] = stats.get(key, 0) + 1
    for ambiguity in ambiguous:
        key = f"ambiguous:{ambiguity.family}"
        stats[key] = stats.get(key, 0) + 1
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
    plan = discover_area_poi_plan(str(source), osmium)
    if reporter is not None:
        reporter(
            "Area POI: "
            f"synthesize {len(plan.synthetic):,}; "
            f"merge {len(plan.enrichments):,}; ambiguous {len(plan.ambiguous):,}"
        )
    return write_area_pois(
        source,
        output_path,
        plan.synthetic,
        osmium,
        reporter=reporter,
        enrichments=plan.enrichments,
        ambiguous=plan.ambiguous,
    )

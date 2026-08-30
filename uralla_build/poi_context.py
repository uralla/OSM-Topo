"""Prototype spatial context scoring for tourist-useful food shops.

The first version intentionally indexes only node-based food shops. This keeps
normal preprocessing memory usage low while we validate whether local rarity is
a useful Garmin LOD signal. A persistent territorial index can replace this
in-memory first pass later without changing the semantic tags consumed by the
style.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import asin, cos, floor, radians, sin, sqrt
from typing import Any, Iterable, Mapping


ACCOMMODATION_VALUES = frozenset({"hotel", "hostel", "guest_house"})
TRANSIT_STOP_HIGHWAYS = frozenset({"bus_stop"})


FOOD_SHOP_VALUES = frozenset(
    {
        "supermarket",
        "convenience",
        "general",
        "grocery",
        "bakers",
        "bakery",
        "butcher",
        "organic",
    }
)
POI_CONTEXT_TAG = "uralla:poi_context"
POI_PRIORITY_TAG = "uralla:poi_priority"
POI_NEAR_2KM_TAG = "uralla:poi_food_2km"
POI_NEAR_10KM_TAG = "uralla:poi_food_10km"
GRID_DEGREES = 0.05
EARTH_RADIUS_KM = 6371.0088


def is_food_shop(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    return values.get("shop") in FOOD_SHOP_VALUES or values.get("amenity") == "supermarket"


def is_transit_stop(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    if values.get("highway") in TRANSIT_STOP_HIGHWAYS:
        return True
    return (
        values.get("public_transport") == "platform"
        and (values.get("bus") == "yes" or values.get("trolleybus") == "yes")
    )


def classify_transit_stop(*, stops_2km: int) -> tuple[str, str]:
    # A stop is useful farther out when it is not part of a dense urban stop grid.
    if stops_2km <= 2:
        return "remote", "isolated"
    if stops_2km <= 6:
        return "settlement", "sparse"
    return "urban", "common"


def is_accommodation(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    return values.get("tourism") in ACCOMMODATION_VALUES


def classify_accommodation(*, objects_2km: int, objects_10km: int) -> tuple[str, str]:
    if objects_2km <= 1 and objects_10km <= 10:
        return "remote", "isolated"
    if objects_2km <= 3 and objects_10km <= 25:
        return "settlement", "sparse"
    return "urban", "common"


def classify_food_shop(*, shops_2km: int, shops_10km: int) -> tuple[str, str]:
    """Return (context, priority) from local food-shop rarity.

    Counts include the shop being classified. The 2 km radius is the primary
    local-density signal; the 10 km radius is deliberately permissive so a
    nearby town or city does not hide a genuinely remote tourist-useful POI.
    Thresholds are still experimental and tuned from real Garmin map tests.
    """

    if shops_2km <= 1 and shops_10km <= 10:
        return "remote", "isolated"
    if shops_2km <= 3 and shops_10km <= 25:
        return "settlement", "sparse"
    return "urban", "common"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1 = radians(lat1)
    p2 = radians(lat2)
    dlat = p2 - p1
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2.0) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * asin(sqrt(a))


@dataclass(slots=True)
class FoodShopIndex:
    """Small in-memory grid for node-shop proximity queries."""

    cells: dict[tuple[int, int], list[tuple[float, float]]]
    shop_count: int = 0

    @classmethod
    def empty(cls) -> "FoodShopIndex":
        return cls(defaultdict(list), 0)

    @staticmethod
    def _cell(lat: float, lon: float) -> tuple[int, int]:
        return floor(lat / GRID_DEGREES), floor(lon / GRID_DEGREES)

    def add(self, lat: float, lon: float) -> None:
        self.cells[self._cell(lat, lon)].append((lat, lon))
        self.shop_count += 1

    def count_within(self, lat: float, lon: float, radius_km: float) -> int:
        lat_delta = radius_km / 110.574
        lon_scale = max(111.320 * abs(cos(radians(lat))), 1.0)
        lon_delta = radius_km / lon_scale
        min_y = floor((lat - lat_delta) / GRID_DEGREES)
        max_y = floor((lat + lat_delta) / GRID_DEGREES)
        min_x = floor((lon - lon_delta) / GRID_DEGREES)
        max_x = floor((lon + lon_delta) / GRID_DEGREES)
        total = 0
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                for candidate_lat, candidate_lon in self.cells.get((y, x), ()):
                    if _haversine_km(lat, lon, candidate_lat, candidate_lon) <= radius_km:
                        total += 1
        return total


def valid_node_location(item: object) -> tuple[float, float] | None:
    """Return (lat, lon) for a node-like object, otherwise None."""

    location = getattr(item, "location", None)
    if location is None:
        return None
    valid = getattr(location, "valid", None)
    if callable(valid) and not valid():
        return None
    try:
        return float(location.lat), float(location.lon)
    except (AttributeError, TypeError, ValueError):
        return None


def build_food_shop_index(source: str, osmium: Any) -> FoodShopIndex:
    """Scan a PBF once and index node-based food shops only."""

    index = FoodShopIndex.empty()
    for item in osmium.FileProcessor(source):
        if not is_food_shop(item.tags):
            continue
        location = valid_node_location(item)
        if location is None:
            continue
        index.add(*location)
    return index


def build_transit_stop_index(source: str, osmium: Any) -> FoodShopIndex:
    index = FoodShopIndex.empty()
    for item in osmium.FileProcessor(source):
        if not is_transit_stop(item.tags):
            continue
        location = valid_node_location(item)
        if location is not None:
            index.add(*location)
    return index


def enrich_transit_stop_context(
    item: object,
    tags: Mapping[str, str] | object,
    index: FoodShopIndex,
) -> tuple[dict[str, str], bool, dict[str, object] | None]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if not is_transit_stop(result):
        return result, False, None
    location = valid_node_location(item)
    if location is None:
        return result, False, None
    lat, lon = location
    stops_2km = index.count_within(lat, lon, 2.0)
    context, priority = classify_transit_stop(stops_2km=stops_2km)
    desired = {
        POI_CONTEXT_TAG: context,
        POI_PRIORITY_TAG: priority,
        "uralla:poi_transit_2km": str(stops_2km),
    }
    changed = any(result.get(key) != value for key, value in desired.items())
    result.update(desired)
    return result, changed, {
        "id": int(getattr(item, "id", 0)),
        "name": result.get("name"),
        "context": context,
        "priority": priority,
        "stops_2km": stops_2km,
        "lat": lat,
        "lon": lon,
    }


def build_accommodation_index(source: str, osmium: Any) -> FoodShopIndex:
    index = FoodShopIndex.empty()
    for item in osmium.FileProcessor(source):
        if not is_accommodation(item.tags):
            continue
        location = valid_node_location(item)
        if location is not None:
            index.add(*location)
    return index


def nearest_accommodation_details(
    source: str,
    osmium: Any,
    lat: float,
    lon: float,
    limit: int = 20,
) -> list[dict[str, object]]:
    """Diagnostic-only full scan returning nearest node accommodations."""

    rows: list[dict[str, object]] = []
    for item in osmium.FileProcessor(source):
        if not is_accommodation(item.tags):
            continue
        location = valid_node_location(item)
        if location is None:
            continue
        candidate_lat, candidate_lon = location
        distance_km = _haversine_km(lat, lon, candidate_lat, candidate_lon)
        tags = {str(key): str(value) for key, value in item.tags}
        rows.append(
            {
                "id": int(getattr(item, "id", 0)),
                "name": tags.get("name"),
                "tourism": tags.get("tourism"),
                "lat": candidate_lat,
                "lon": candidate_lon,
                "distance_km": distance_km,
            }
        )
    rows.sort(key=lambda row: float(row["distance_km"]))
    return rows[:limit]


def enrich_accommodation_context(
    item: object,
    tags: Mapping[str, str] | object,
    index: FoodShopIndex,
) -> tuple[dict[str, str], bool, dict[str, object] | None]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if not is_accommodation(result):
        return result, False, None
    location = valid_node_location(item)
    if location is None:
        return result, False, None
    lat, lon = location
    objects_2km = index.count_within(lat, lon, 2.0)
    objects_10km = index.count_within(lat, lon, 10.0)
    context, priority = classify_accommodation(objects_2km=objects_2km, objects_10km=objects_10km)
    desired = {
        POI_CONTEXT_TAG: context,
        POI_PRIORITY_TAG: priority,
        "uralla:poi_accommodation_2km": str(objects_2km),
        "uralla:poi_accommodation_10km": str(objects_10km),
    }
    changed = any(result.get(key) != value for key, value in desired.items())
    result.update(desired)
    return result, changed, {
        "id": int(getattr(item, "id", 0)), "name": result.get("name"),
        "tourism": result.get("tourism"), "context": context, "priority": priority,
        "objects_2km": objects_2km, "objects_10km": objects_10km, "lat": lat, "lon": lon,
    }


def enrich_food_shop_context(
    item: object,
    tags: Mapping[str, str] | object,
    index: FoodShopIndex,
) -> tuple[dict[str, str], bool, dict[str, object] | None]:
    """Attach prototype context tags to node food shops."""

    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if not is_food_shop(result):
        return result, False, None
    location = valid_node_location(item)
    if location is None:
        return result, False, None
    lat, lon = location
    shops_2km = index.count_within(lat, lon, 2.0)
    shops_10km = index.count_within(lat, lon, 10.0)
    context, priority = classify_food_shop(shops_2km=shops_2km, shops_10km=shops_10km)
    desired = {
        POI_CONTEXT_TAG: context,
        POI_PRIORITY_TAG: priority,
        POI_NEAR_2KM_TAG: str(shops_2km),
        POI_NEAR_10KM_TAG: str(shops_10km),
    }
    changed = any(result.get(key) != value for key, value in desired.items())
    result.update(desired)
    sample = {
        "id": int(getattr(item, "id", 0)),
        "name": result.get("name"),
        "shop": result.get("shop") or result.get("amenity"),
        "context": context,
        "priority": priority,
        "shops_2km": shops_2km,
        "shops_10km": shops_10km,
        "lat": lat,
        "lon": lon,
    }
    return result, changed, sample

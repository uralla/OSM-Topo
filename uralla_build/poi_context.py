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

from .poi_lod import POI_LOD_CLASS_TAG, classify_poi_lod, intrinsic_floor_for_poi


ACCOMMODATION_VALUES = frozenset({"hotel", "hostel", "guest_house"})
TRANSIT_STOP_HIGHWAYS = frozenset({"bus_stop"})
PICNIC_SITE_VALUES = frozenset({"picnic_site"})
OUTDOOR_FURNITURE_VALUES = frozenset({"bench", "picnic_table"})
TOURIST_RETAIL_VALUES = frozenset({"bicycle", "hardware", "doityourself", "houseware", "sports", "outdoor"})
SETTLEMENT_PLACE_VALUES = frozenset({"city", "town", "village", "hamlet"})
ACTIVITY_PLACE_GUARD_RADII_KM = {"city": 7.0, "town": 5.0, "village": 2.0, "hamlet": 1.0}


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
POI_ACTIVITY_500M_TAG = "uralla:poi_activity_500m"
POI_ACTIVITY_2KM_TAG = "uralla:poi_activity_2km"
POI_ACTIVITY_10KM_TAG = "uralla:poi_activity_10km"
POI_ACTIVITY_CONTEXT_TAG = "uralla:poi_activity_context"
POI_SCREEN_PRESSURE_TAG = "uralla:poi_screen_pressure"
POI_SCREEN_PRESSURE_2KM_TAG = "uralla:poi_screen_pressure_2km"
POI_SCREEN_PRESSURE_10KM_TAG = "uralla:poi_screen_pressure_10km"
SCREEN_PRESSURE_PRIMARY_KEYS = frozenset({"amenity", "tourism", "shop", "historic", "natural", "man_made", "leisure", "highway", "railway", "aeroway", "craft", "emergency", "power", "barrier", "traffic_sign", "whitewater", "office", "landuse", "military", "sport", "place"})
CONTEXT_METADATA_KEYS = frozenset({"source", "created_by", "attribution", "note", "fixme", "check_date", "survey:date"})
GRID_DEGREES = 0.05
EARTH_RADIUS_KM = 6371.0088


def is_meaningful_context_node(tags: Mapping[str, str] | object) -> bool:
    """Return True for a tagged node carrying real map semantics.

    Untagged geometry vertices never reach this predicate as meaningful context;
    metadata-only nodes are excluded so detailed geometry cannot fake urban density.
    """

    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    for raw_key, raw_value in items:
        key = str(raw_key)
        value = str(raw_value)
        if not value:
            continue
        if key in CONTEXT_METADATA_KEYS:
            continue
        if key.startswith(("source:", "note:", "fixme:", "check_date:")):
            continue
        return True
    return False


def screen_pressure_weight(tags: Mapping[str, str] | object) -> int:
    """Approximate how much a node competes for Garmin screen space.

    This deliberately ignores address/metadata-only nodes. A generic render-like POI
    weighs 1, a named POI weighs 2, and settlement place labels weigh 4. The style
    does not consume this signal yet; it is diagnostic while we validate the model.
    """
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    if not any(values.get(key) for key in SCREEN_PRESSURE_PRIMARY_KEYS):
        return 0
    if values.get("place") in SETTLEMENT_PLACE_VALUES:
        return 4
    return 2 if (values.get("name") or values.get("name:ru")) else 1


def classify_screen_pressure(
    *,
    pressure_2km: int,
    pressure_10km: int,
    local_p25: int,
    local_p75: int,
    background_p25: int,
    background_p75: int,
) -> str:
    # Screen pressure is intentionally local-first: the 2 km neighborhood
    # represents immediate visual competition. The 10 km background is only a
    # guard against calling a locally sparse pocket "low" inside an already
    # very dense wider area.
    if pressure_2km <= local_p25 and pressure_10km < background_p75:
        return "low"
    if pressure_2km >= local_p75 and pressure_10km >= background_p75:
        return "high"
    return "medium"


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


def is_picnic_site(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    return values.get("tourism") in PICNIC_SITE_VALUES


def is_outdoor_furniture(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    return values.get("amenity") == "bench" or values.get("leisure") == "picnic_table"


def is_tourist_retail(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    return values.get("shop") in TOURIST_RETAIL_VALUES


def is_kitesurfing(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    return values.get("sport") == "kitesurfing"


def is_spring(tags: Mapping[str, str] | object) -> bool:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    values = {str(key): str(value) for key, value in items}
    return values.get("natural") == "spring"


def classify_outdoor_rarity(*, objects_2km: int, objects_10km: int) -> tuple[str, str]:
    if objects_2km <= 1 and objects_10km <= 10:
        return "remote", "isolated"
    if objects_2km <= 3 and objects_10km <= 25:
        return "settlement", "sparse"
    return "urban", "common"


def classify_activity_context(
    *,
    activity_2km: int,
    activity_10km: int,
    local_p25: int,
    local_p75: int,
    background_p25: int,
    background_p75: int,
) -> str:
    """Classify general activity context from territory-relative density bands."""
    if activity_2km <= local_p25 and activity_10km <= background_p25:
        return "remote"
    if activity_2km >= local_p75 and activity_10km >= background_p75:
        return "urban"
    return "settlement"


def apply_activity_place_guard(
    context: str,
    place_by_type: Mapping[str, object] | None,
) -> str:
    """Raise density-remote POIs to settlement when a nearby place anchor says so."""
    if context != "remote" or not place_by_type:
        return context
    for place_type, radius_km in ACTIVITY_PLACE_GUARD_RADII_KM.items():
        raw = place_by_type.get(place_type)
        if not isinstance(raw, Mapping):
            continue
        distance = raw.get("distance_km")
        if distance is not None and float(distance) <= radius_km:
            return "settlement"
    return "remote"


def classify_activity_context_with_place_guard(
    *,
    activity_2km: int,
    activity_10km: int,
    local_p25: int,
    local_p75: int,
    background_p25: int,
    background_p75: int,
    place_by_type: Mapping[str, object] | None,
) -> str:
    context = classify_activity_context(
        activity_2km=activity_2km,
        activity_10km=activity_10km,
        local_p25=local_p25,
        local_p75=local_p75,
        background_p25=background_p25,
        background_p75=background_p75,
    )
    return apply_activity_place_guard(context, place_by_type)


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


    def count_cells_within_circle(self, lat: float, lon: float, radius_km: float) -> int:
        """Fast approximate wide-area count using grid cells whose centers are in range."""
        lat_delta = radius_km / 110.574
        lon_scale = max(111.320 * abs(cos(radians(lat))), 1.0)
        lon_delta = radius_km / lon_scale
        min_y = floor((lat - lat_delta) / GRID_DEGREES)
        max_y = floor((lat + lat_delta) / GRID_DEGREES)
        min_x = floor((lon - lon_delta) / GRID_DEGREES)
        max_x = floor((lon + lon_delta) / GRID_DEGREES)
        total = 0
        for y in range(min_y, max_y + 1):
            center_lat = (y + 0.5) * GRID_DEGREES
            for x in range(min_x, max_x + 1):
                center_lon = (x + 0.5) * GRID_DEGREES
                if _haversine_km(lat, lon, center_lat, center_lon) <= radius_km:
                    total += len(self.cells.get((y, x), ()))
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


@dataclass(slots=True)
class WeightedPointIndex:
    cells: dict[tuple[int, int], list[tuple[float, float, int]]]
    point_count: int = 0
    total_weight: int = 0

    @classmethod
    def empty(cls) -> "WeightedPointIndex":
        return cls(defaultdict(list), 0, 0)

    @staticmethod
    def _cell(lat: float, lon: float) -> tuple[int, int]:
        return floor(lat / GRID_DEGREES), floor(lon / GRID_DEGREES)

    def add(self, lat: float, lon: float, weight: int) -> None:
        if weight <= 0:
            return
        self.cells[self._cell(lat, lon)].append((lat, lon, int(weight)))
        self.point_count += 1
        self.total_weight += int(weight)

    def score_within(self, lat: float, lon: float, radius_km: float) -> int:
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
                for candidate_lat, candidate_lon, weight in self.cells.get((y, x), ()):
                    if _haversine_km(lat, lon, candidate_lat, candidate_lon) <= radius_km:
                        total += weight
        return total

    def score_cells_within_circle(self, lat: float, lon: float, radius_km: float) -> int:
        lat_delta = radius_km / 110.574
        lon_scale = max(111.320 * abs(cos(radians(lat))), 1.0)
        lon_delta = radius_km / lon_scale
        min_y = floor((lat - lat_delta) / GRID_DEGREES)
        max_y = floor((lat + lat_delta) / GRID_DEGREES)
        min_x = floor((lon - lon_delta) / GRID_DEGREES)
        max_x = floor((lon + lon_delta) / GRID_DEGREES)
        total = 0
        for y in range(min_y, max_y + 1):
            center_lat = (y + 0.5) * GRID_DEGREES
            for x in range(min_x, max_x + 1):
                center_lon = (x + 0.5) * GRID_DEGREES
                if _haversine_km(lat, lon, center_lat, center_lon) <= radius_km:
                    total += sum(weight for _lat, _lon, weight in self.cells.get((y, x), ()))
        return total


@dataclass(slots=True)
class PlaceAnchorIndex:
    cells: dict[tuple[int, int], list[tuple[float, float, str, str | None]]]
    anchor_count: int = 0

    @classmethod
    def empty(cls) -> "PlaceAnchorIndex":
        return cls(defaultdict(list), 0)

    @staticmethod
    def _cell(lat: float, lon: float) -> tuple[int, int]:
        return floor(lat / GRID_DEGREES), floor(lon / GRID_DEGREES)

    def add(self, lat: float, lon: float, place_type: str, name: str | None) -> None:
        self.cells[self._cell(lat, lon)].append((lat, lon, place_type, name))
        self.anchor_count += 1

    def nearest_within(
        self, lat: float, lon: float, radius_km: float
    ) -> tuple[float, str, str | None] | None:
        lat_delta = radius_km / 110.574
        lon_scale = max(111.320 * abs(cos(radians(lat))), 1.0)
        lon_delta = radius_km / lon_scale
        min_y = floor((lat - lat_delta) / GRID_DEGREES)
        max_y = floor((lat + lat_delta) / GRID_DEGREES)
        min_x = floor((lon - lon_delta) / GRID_DEGREES)
        max_x = floor((lon + lon_delta) / GRID_DEGREES)
        nearest: tuple[float, str, str | None] | None = None
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                for candidate_lat, candidate_lon, place_type, name in self.cells.get((y, x), ()):
                    distance = _haversine_km(lat, lon, candidate_lat, candidate_lon)
                    if distance <= radius_km and (nearest is None or distance < nearest[0]):
                        nearest = (distance, place_type, name)
        return nearest

    def nearest_by_type_within(
        self, lat: float, lon: float, radius_km: float
    ) -> dict[str, tuple[float, str | None]]:
        lat_delta = radius_km / 110.574
        lon_scale = max(111.320 * abs(cos(radians(lat))), 1.0)
        lon_delta = radius_km / lon_scale
        min_y = floor((lat - lat_delta) / GRID_DEGREES)
        max_y = floor((lat + lat_delta) / GRID_DEGREES)
        min_x = floor((lon - lon_delta) / GRID_DEGREES)
        max_x = floor((lon + lon_delta) / GRID_DEGREES)
        nearest: dict[str, tuple[float, str | None]] = {}
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                for candidate_lat, candidate_lon, place_type, name in self.cells.get((y, x), ()):
                    distance = _haversine_km(lat, lon, candidate_lat, candidate_lon)
                    current = nearest.get(place_type)
                    if distance <= radius_km and (current is None or distance < current[0]):
                        nearest[place_type] = (distance, name)
        return nearest


@dataclass(slots=True)
class ContextIndexes:
    food: FoodShopIndex
    accommodation: FoodShopIndex
    transit: FoodShopIndex
    picnic: FoodShopIndex
    outdoor_furniture: FoodShopIndex
    tourist_retail: FoodShopIndex
    kitesurfing: FoodShopIndex
    spring: FoodShopIndex
    activity: FoodShopIndex
    screen_pressure: WeightedPointIndex
    places: PlaceAnchorIndex
    adaptive_candidates: list[tuple[int, float, float]]


def build_context_indexes(source: str, osmium: Any) -> ContextIndexes:
    """Build all current node context indexes in one PBF pass."""

    food = FoodShopIndex.empty()
    accommodation = FoodShopIndex.empty()
    transit = FoodShopIndex.empty()
    picnic = FoodShopIndex.empty()
    outdoor_furniture = FoodShopIndex.empty()
    tourist_retail = FoodShopIndex.empty()
    kitesurfing = FoodShopIndex.empty()
    spring = FoodShopIndex.empty()
    activity = FoodShopIndex.empty()
    screen_pressure = WeightedPointIndex.empty()
    places = PlaceAnchorIndex.empty()
    adaptive_candidates: list[tuple[int, float, float]] = []
    for item in osmium.FileProcessor(source):
        location = valid_node_location(item)
        if location is None:
            continue
        tags = {str(key): str(value) for key, value in item.tags}
        if is_meaningful_context_node(tags):
            activity.add(*location)
        pressure_weight = screen_pressure_weight(tags)
        if pressure_weight:
            screen_pressure.add(*location, pressure_weight)
        adaptive = False
        if is_food_shop(tags):
            food.add(*location)
            adaptive = True
        if is_accommodation(tags):
            accommodation.add(*location)
            adaptive = True
        if is_transit_stop(tags):
            transit.add(*location)
            adaptive = True
        if is_picnic_site(tags):
            picnic.add(*location)
            adaptive = True
        if is_outdoor_furniture(tags):
            outdoor_furniture.add(*location)
            adaptive = True
        if is_tourist_retail(tags):
            tourist_retail.add(*location)
            adaptive = True
        if is_kitesurfing(tags):
            kitesurfing.add(*location)
            adaptive = True
        if is_spring(tags):
            spring.add(*location)
            adaptive = True
        if adaptive:
            adaptive_candidates.append((int(getattr(item, "id", 0)), location[0], location[1]))
        place_type = tags.get("place")
        if place_type in SETTLEMENT_PLACE_VALUES:
            places.add(*location, place_type, tags.get("name") or tags.get("name:ru"))
    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, tourist_retail, kitesurfing, spring, activity, screen_pressure, places, adaptive_candidates)


def enrich_outdoor_context(
    item: object,
    tags: Mapping[str, str] | object,
    index: FoodShopIndex,
    *,
    kind: str,
) -> tuple[dict[str, str], bool, dict[str, object] | None]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if kind == "picnic":
        matches = is_picnic_site(result)
    elif kind == "furniture":
        matches = is_outdoor_furniture(result)
    elif kind == "retail":
        matches = is_tourist_retail(result)
    elif kind == "kitesurfing":
        matches = is_kitesurfing(result)
    elif kind == "spring":
        matches = is_spring(result)
    else:
        raise ValueError(f"unknown outdoor context kind: {kind}")
    if not matches:
        return result, False, None
    location = valid_node_location(item)
    if location is None:
        return result, False, None
    lat, lon = location
    objects_2km = index.count_within(lat, lon, 2.0)
    objects_10km = index.count_within(lat, lon, 10.0)
    context, priority = classify_outdoor_rarity(objects_2km=objects_2km, objects_10km=objects_10km)
    desired = {
        POI_CONTEXT_TAG: context,
        POI_PRIORITY_TAG: priority,
        f"uralla:poi_{kind}_2km": str(objects_2km),
        f"uralla:poi_{kind}_10km": str(objects_10km),
    }
    changed = any(result.get(key) != value for key, value in desired.items())
    result.update(desired)
    return result, changed, {
        "id": int(getattr(item, "id", 0)),
        "name": result.get("name"),
        "kind": kind,
        "context": context,
        "priority": priority,
        "objects_2km": objects_2km,
        "objects_10km": objects_10km,
        "lat": lat,
        "lon": lon,
    }



def enrich_activity_diagnostics(
    item: object,
    tags: Mapping[str, str] | object,
    index: FoodShopIndex,
    places: PlaceAnchorIndex,
    thresholds: Mapping[str, int] | None = None,
    screen_index: WeightedPointIndex | None = None,
    screen_thresholds: Mapping[str, int] | None = None,
) -> tuple[dict[str, str], bool, dict[str, object] | None]:
    """Attach general human-activity density diagnostics to context-aware POIs."""

    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if POI_PRIORITY_TAG not in result:
        return result, False, None
    location = valid_node_location(item)
    if location is None:
        return result, False, None
    lat, lon = location
    activity_500m = index.count_within(lat, lon, 0.5)
    activity_2km = index.count_within(lat, lon, 2.0)
    activity_10km = index.count_cells_within_circle(lat, lon, 10.0)
    nearest_place = places.nearest_within(lat, lon, 10.0)
    nearest_places_by_type = places.nearest_by_type_within(lat, lon, 10.0)
    desired = {
        POI_ACTIVITY_500M_TAG: str(activity_500m),
        POI_ACTIVITY_2KM_TAG: str(activity_2km),
        POI_ACTIVITY_10KM_TAG: str(activity_10km),
    }
    if thresholds is not None:
        final_context = classify_activity_context_with_place_guard(
            activity_2km=activity_2km,
            activity_10km=activity_10km,
            local_p25=int(thresholds["2km_p25"]),
            local_p75=int(thresholds["2km_p75"]),
            background_p25=int(thresholds["10km_p25"]),
            background_p75=int(thresholds["10km_p75"]),
            place_by_type={
                key: {"distance_km": value[0], "name": value[1]}
                for key, value in nearest_places_by_type.items()
            },
        )
        desired[POI_ACTIVITY_CONTEXT_TAG] = final_context
    screen_2km = None
    screen_10km = None
    screen_context = None
    if screen_index is not None:
        screen_2km = screen_index.score_within(lat, lon, 2.0)
        screen_10km = screen_index.score_cells_within_circle(lat, lon, 10.0)
        desired[POI_SCREEN_PRESSURE_2KM_TAG] = str(screen_2km)
        desired[POI_SCREEN_PRESSURE_10KM_TAG] = str(screen_10km)
        if screen_thresholds is not None:
            screen_context = classify_screen_pressure(
                pressure_2km=screen_2km,
                pressure_10km=screen_10km,
                local_p25=int(screen_thresholds["2km_p25"]),
                local_p75=int(screen_thresholds["2km_p75"]),
                background_p25=int(screen_thresholds["10km_p25"]),
                background_p75=int(screen_thresholds["10km_p75"]),
            )
            desired[POI_SCREEN_PRESSURE_TAG] = screen_context

    lod_class = None
    activity_context = desired.get(POI_ACTIVITY_CONTEXT_TAG) or result.get(POI_ACTIVITY_CONTEXT_TAG)
    if activity_context and screen_context:
        lod_class = classify_poi_lod(
            priority=result.get(POI_PRIORITY_TAG, "common"),
            activity_context=activity_context,
            screen_pressure=screen_context,
            intrinsic_floor=intrinsic_floor_for_poi(result),
        )
        desired[POI_LOD_CLASS_TAG] = lod_class

    changed = any(result.get(key) != value for key, value in desired.items())
    result.update(desired)
    if is_food_shop(result):
        poi_kind = "food"
    elif is_accommodation(result):
        poi_kind = "accommodation"
    elif is_transit_stop(result):
        poi_kind = "transit"
    else:
        poi_kind = "other"
    return result, changed, {
        "id": int(getattr(item, "id", 0)),
        "name": result.get("name"),
        "kind": poi_kind,
        "priority": result.get(POI_PRIORITY_TAG),
        "activity_500m": activity_500m,
        "activity_2km": activity_2km,
        "activity_10km": activity_10km,
        "screen_pressure_2km": screen_2km,
        "screen_pressure_10km": screen_10km,
        "screen_pressure": screen_context,
        "lod_class": lod_class,
        "intrinsic_floor": intrinsic_floor_for_poi(result),
        "place_distance_km": nearest_place[0] if nearest_place is not None else None,
        "place_type": nearest_place[1] if nearest_place is not None else None,
        "place_name": nearest_place[2] if nearest_place is not None else None,
        "place_by_type": {key: {"distance_km": value[0], "name": value[1]} for key, value in nearest_places_by_type.items()},
        "lat": lat,
        "lon": lon,
    }


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

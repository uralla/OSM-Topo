"""Local ranking for small-settlement overview labels.

The Garmin overview should prefer real settlements over weaker locality anchors while
still allowing a lone remote object to appear early. Ranking is intentionally local:
within 10 km we count only small settlements that outrank the current object.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


SETTLEMENT_LOD_TAG = "uralla:settlement_lod"
SETTLEMENT_RADIUS_KM = 10.0
SETTLEMENT_GRID_DEGREES = 0.1
SMALL_SETTLEMENT_VALUES = frozenset(
    {"village", "hamlet", "isolated_dwelling", "farm", "locality"}
)

# User-facing importance hierarchy. The bottom three classes are deliberately equal.
_SETTLEMENT_CLASS_PRIORITY = {
    "village": 3,
    "hamlet": 2,
    "isolated_dwelling": 1,
    "farm": 1,
    "locality": 1,
}


@dataclass(frozen=True, slots=True)
class SettlementCandidate:
    osm_id: int
    lat: float
    lon: float
    place: str
    population: int

    @property
    def priority_key(self) -> tuple[int, int, int]:
        # Smaller tuple means higher visual priority. Class wins first, then
        # population, then a stable OSM-id tie break.
        return (
            -_SETTLEMENT_CLASS_PRIORITY[self.place],
            -self.population,
            self.osm_id,
        )


def _tags_dict(tags: Mapping[str, str] | object) -> dict[str, str]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    return {str(key): str(value) for key, value in items}


def _population(value: str | None) -> int:
    if not value:
        return 0
    compact = value.replace(" ", "").replace(",", "").replace("_", "")
    try:
        number = int(compact)
    except ValueError:
        return 0
    return max(0, number)


def _location(item: object) -> tuple[float, float] | None:
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


def _distance_km(a: SettlementCandidate, b: SettlementCandidate) -> float:
    radius = 6371.0088
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    value = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(value)))


def _grid_key(lat: float, lon: float) -> tuple[int, int]:
    return (
        math.floor(lat / SETTLEMENT_GRID_DEGREES),
        math.floor(lon / SETTLEMENT_GRID_DEGREES),
    )


def _lod_from_higher_count(count: int) -> int:
    """Spread local labels progressively over Garmin overview resolutions."""
    if count <= 0:
        return 19
    if count == 1:
        return 20
    if count <= 3:
        return 21
    if count <= 7:
        return 22
    return 23


def rank_settlement_candidates(
    candidates: list[SettlementCandidate],
) -> tuple[dict[int, int], Counter[int]]:
    """Return OSM node -> LOD using only nearby higher-priority settlements."""
    grid: dict[tuple[int, int], list[SettlementCandidate]] = defaultdict(list)
    for candidate in candidates:
        grid[_grid_key(candidate.lat, candidate.lon)].append(candidate)

    lods: dict[int, int] = {}
    counts: Counter[int] = Counter()
    for candidate in candidates:
        y, x = _grid_key(candidate.lat, candidate.lon)
        lat_cells = max(1, math.ceil(SETTLEMENT_RADIUS_KM / (111.32 * SETTLEMENT_GRID_DEGREES))) + 1
        lon_scale = max(math.cos(math.radians(candidate.lat)), 0.05)
        lon_cells = max(
            1,
            math.ceil(
                SETTLEMENT_RADIUS_KM
                / (111.32 * lon_scale * SETTLEMENT_GRID_DEGREES)
            )
            + 1,
        )
        higher = 0
        for dy in range(-lat_cells, lat_cells + 1):
            for dx in range(-lon_cells, lon_cells + 1):
                for other in grid.get((y + dy, x + dx), ()):  # type: ignore[arg-type]
                    if other.osm_id == candidate.osm_id:
                        continue
                    if other.priority_key >= candidate.priority_key:
                        continue
                    if _distance_km(candidate, other) <= SETTLEMENT_RADIUS_KM:
                        higher += 1
        lod = _lod_from_higher_count(higher)
        lods[candidate.osm_id] = lod
        counts[lod] += 1
    return lods, counts


def analyze_settlement_lods(
    input_path: str | Path,
    osmium: Any,
) -> tuple[dict[int, int], dict[str, int]]:
    """Collect named small-settlement nodes and assign deterministic local LODs."""
    source = Path(input_path).resolve()
    candidates: list[SettlementCandidate] = []
    for item in osmium.FileProcessor(str(source)):
        type_method = getattr(item, "type_str", None)
        kind = type_method() if callable(type_method) else ""
        if kind not in {"node", "n"}:
            continue
        tags = _tags_dict(item.tags)
        place = tags.get("place")
        if place not in SMALL_SETTLEMENT_VALUES:
            continue
        if not (tags.get("name") or tags.get("name:ru")):
            continue
        location = _location(item)
        if location is None:
            continue
        lat, lon = location
        candidates.append(
            SettlementCandidate(
                osm_id=int(item.id),
                lat=lat,
                lon=lon,
                place=place,
                population=_population(tags.get("population")),
            )
        )

    lods, counts = rank_settlement_candidates(candidates)
    stats = {
        "candidates": len(candidates),
        "lod19": counts[19],
        "lod20": counts[20],
        "lod21": counts[21],
        "lod22": counts[22],
        "lod23": counts[23],
    }
    return lods, stats


def augment_settlement_lods(
    input_path: str | Path,
    output_path: str | Path,
    osmium: Any,
    *,
    reporter: Any = None,
) -> dict[str, int]:
    """Apply the same settlement ranking used by fast ANALYZE/APPLY to a PBF."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    if source == target:
        raise ValueError("settlement LOD input and output must be different files")
    lods, stats = analyze_settlement_lods(source, osmium)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.settlement-lod.partial.osm.pbf"
    tagged = 0
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)):
                type_method = getattr(item, "type_str", None)
                kind = type_method() if callable(type_method) else ""
                if kind not in {"node", "n"}:
                    writer.add(item)
                    continue
                lod = lods.get(int(item.id))
                if lod is None:
                    writer.add(item)
                    continue
                tags = _tags_dict(item.tags)
                value = str(lod)
                if tags.get(SETTLEMENT_LOD_TAG) != value:
                    tags[SETTLEMENT_LOD_TAG] = value
                    writer.add(item.replace(tags=tags))
                    tagged += 1
                else:
                    writer.add(item)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    result = dict(stats)
    result["tagged"] = tagged
    if reporter is not None:
        reporter(
            "Settlement LOD applied: "
            f"candidates {stats['candidates']:,}; 19={stats['lod19']:,} "
            f"20={stats['lod20']:,} 21={stats['lod21']:,} "
            f"22={stats['lod22']:,} 23={stats['lod23']:,}"
        )
    return result

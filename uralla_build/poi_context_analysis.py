"""Reusable POI/activity context analysis artifact for analyze/apply preprocessing."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .errors import StageError
from .poi_context import (
    POI_ACTIVITY_CONTEXT_TAG,
    POI_ACTIVITY_10KM_TAG,
    POI_ACTIVITY_2KM_TAG,
    POI_ACTIVITY_500M_TAG,
    POI_CONTEXT_TAG,
    POI_NEAR_10KM_TAG,
    POI_NEAR_2KM_TAG,
    POI_PRIORITY_TAG,
    POI_SCREEN_PRESSURE_10KM_TAG,
    POI_SCREEN_PRESSURE_2KM_TAG,
    POI_SCREEN_PRESSURE_TAG,
    build_context_indexes,
    enrich_accommodation_context,
    enrich_activity_diagnostics,
    enrich_food_shop_context,
    enrich_outdoor_context,
    enrich_transit_stop_context,
    is_accommodation,
    is_food_shop,
    is_kitesurfing,
    is_outdoor_furniture,
    is_picnic_site,
    is_spring,
    is_tourist_retail,
    is_transit_stop,
)
from .poi_lod import POI_LOD_CLASS_TAG

SCHEMA_VERSION = 4
ANALYSIS_KIND = "poi_context"
SMALL_SETTLEMENT_VALUES = frozenset(
    {"village", "hamlet", "isolated_dwelling", "locality", "farm"}
)

# Keys that determine whether a cached context result is still semantically safe
# to apply to a newer OSM object. Names deliberately do not participate: a rename
# should not invalidate density/context classification. Place/population do matter
# for settlement LOD because they determine its visual priority.
_SIGNATURE_KEYS = (
    "amenity",
    "shop",
    "tourism",
    "highway",
    "public_transport",
    "bus",
    "trolleybus",
    "leisure",
    "natural",
    "man_made",
    "sport",
    "designation",
    "brand",
    "operator",
    "craft",
    "place",
    "population",
)

_CONTEXT_TAGS = frozenset(
    {
        POI_CONTEXT_TAG,
        POI_PRIORITY_TAG,
        POI_NEAR_2KM_TAG,
        POI_NEAR_10KM_TAG,
        POI_ACTIVITY_500M_TAG,
        POI_ACTIVITY_2KM_TAG,
        POI_ACTIVITY_10KM_TAG,
        POI_ACTIVITY_CONTEXT_TAG,
        POI_SCREEN_PRESSURE_TAG,
        POI_SCREEN_PRESSURE_2KM_TAG,
        POI_SCREEN_PRESSURE_10KM_TAG,
        POI_LOD_CLASS_TAG,
        "uralla:poi_accommodation_2km",
        "uralla:poi_accommodation_10km",
        "uralla:poi_transit_2km",
        "uralla:poi_picnic_2km",
        "uralla:poi_picnic_10km",
        "uralla:poi_furniture_2km",
        "uralla:poi_furniture_10km",
        "uralla:poi_retail_2km",
        "uralla:poi_retail_10km",
        "uralla:poi_kitesurfing_2km",
        "uralla:poi_kitesurfing_10km",
        "uralla:poi_spring_2km",
        "uralla:poi_spring_10km",
    }
)


def _tags_dict(tags: Mapping[str, str] | object) -> dict[str, str]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    return {str(key): str(value) for key, value in items}


def _signature(tags: Mapping[str, str]) -> dict[str, str]:
    return {key: tags[key] for key in _SIGNATURE_KEYS if tags.get(key)}


def _is_antenna(tags: Mapping[str, str]) -> bool:
    return tags.get("man_made") == "antenna"


def _is_small_settlement(tags: Mapping[str, str]) -> bool:
    if tags.get("place") not in SMALL_SETTLEMENT_VALUES:
        return False
    return bool(tags.get("name") or tags.get("name:ru"))


def _is_adaptive(tags: Mapping[str, str]) -> bool:
    return _is_antenna(tags) or _is_small_settlement(tags) or any(
        predicate(tags)
        for predicate in (
            is_food_shop,
            is_accommodation,
            is_transit_stop,
            is_picnic_site,
            is_outdoor_furniture,
            is_tourist_retail,
            is_kitesurfing,
            is_spring,
        )
    )


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def _thresholds(indexes: Any) -> tuple[dict[str, int], dict[str, int]]:
    activity_2km: list[int] = []
    activity_10km: list[int] = []
    screen_2km: list[int] = []
    screen_10km: list[int] = []
    for _node_id, lat, lon in indexes.adaptive_candidates:
        activity_2km.append(indexes.activity.count_within(lat, lon, 2.0))
        activity_10km.append(indexes.activity.count_cells_within_circle(lat, lon, 10.0))
        screen_2km.append(indexes.screen_pressure.score_within(lat, lon, 2.0))
        screen_10km.append(indexes.screen_pressure.score_cells_within_circle(lat, lon, 10.0))
    return (
        {
            "2km_p25": _percentile(activity_2km, 0.25),
            "2km_p75": _percentile(activity_2km, 0.75),
            "10km_p25": _percentile(activity_10km, 0.25),
            "10km_p75": _percentile(activity_10km, 0.75),
        },
        {
            "2km_p25": _percentile(screen_2km, 0.25),
            "2km_p75": _percentile(screen_2km, 0.75),
            "10km_p25": _percentile(screen_10km, 0.25),
            "10km_p75": _percentile(screen_10km, 0.75),
        },
    )


def _enrich_one(item: object, tags: dict[str, str], indexes: Any, activity_thresholds: Mapping[str, int], screen_thresholds: Mapping[str, int]) -> dict[str, str]:
    result, _, _ = enrich_food_shop_context(item, tags, indexes.food)
    result, _, _ = enrich_accommodation_context(item, result, indexes.accommodation)
    result, _, _ = enrich_transit_stop_context(item, result, indexes.transit)
    for index, kind in (
        (indexes.picnic, "picnic"),
        (indexes.outdoor_furniture, "furniture"),
        (indexes.tourist_retail, "retail"),
        (indexes.kitesurfing, "kitesurfing"),
        (indexes.spring, "spring"),
    ):
        result, _, _ = enrich_outdoor_context(item, result, index, kind=kind)

    # Antennas and small settlements join the universal activity/screen-pressure
    # model without inventing a separate density engine. Settlement style consumes
    # screen pressure directly; population remains an independent priority signal.
    if (_is_antenna(result) or _is_small_settlement(result)) and POI_PRIORITY_TAG not in result:
        result[POI_PRIORITY_TAG] = "common"

    result, _, _ = enrich_activity_diagnostics(
        item,
        result,
        indexes.activity,
        indexes.places,
        activity_thresholds,
        indexes.screen_pressure,
        screen_thresholds,
    )
    return result


def save_poi_context_analysis(path: str | Path, payload: dict[str, object]) -> None:
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


def load_poi_context_analysis(path: str | Path) -> dict[str, object]:
    source = Path(path).resolve()
    try:
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StageError(f"cannot load POI-context analysis {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StageError("POI-context analysis root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != ANALYSIS_KIND:
        raise StageError(f"unsupported POI-context analysis artifact: {source}")
    if not isinstance(payload.get("nodes"), dict):
        raise StageError("POI-context analysis nodes must be an object")
    return payload


def analyze_poi_context(input_path: str | Path, output_path: str | Path, osmium: Any, *, reporter: Any = None) -> dict[str, object]:
    """Run expensive spatial POI context analysis and persist reusable node hints."""
    source = Path(input_path).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"POI-context input is missing or empty: {source}")
    if reporter is not None:
        reporter("POI context analysis: building spatial indexes")
    indexes = build_context_indexes(str(source), osmium)
    activity_thresholds, screen_thresholds = _thresholds(indexes)
    nodes: dict[str, dict[str, object]] = {}
    lod_counts: Counter[str] = Counter()
    settlement_pressure: Counter[str] = Counter()
    for item in osmium.FileProcessor(str(source)):
        raw = _tags_dict(item.tags)
        if not _is_adaptive(raw):
            continue
        enriched = _enrich_one(item, raw, indexes, activity_thresholds, screen_thresholds)
        hints = {key: value for key, value in enriched.items() if key in _CONTEXT_TAGS and raw.get(key) != value}
        if not hints:
            continue
        nodes[str(int(item.id))] = {"signature": _signature(raw), "tags": hints}
        lod = hints.get(POI_LOD_CLASS_TAG)
        if lod:
            lod_counts[str(lod)] += 1
        if _is_small_settlement(raw):
            pressure = hints.get(POI_SCREEN_PRESSURE_TAG) or enriched.get(POI_SCREEN_PRESSURE_TAG)
            if pressure:
                settlement_pressure[str(pressure)] += 1
    stat = source.stat()
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {"path": str(source), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        "activity_thresholds": activity_thresholds,
        "screen_thresholds": screen_thresholds,
        "stats": {
            "adaptive_candidates": len(indexes.adaptive_candidates),
            "activity_nodes": indexes.activity.shop_count,
            "screen_nodes": indexes.screen_pressure.point_count,
            "hint_nodes": len(nodes),
            "lod": dict(lod_counts),
            "settlement_pressure": dict(settlement_pressure),
        },
        "nodes": nodes,
    }
    save_poi_context_analysis(output_path, payload)
    if reporter is not None:
        reporter(
            f"POI context analysis saved; hint nodes {len(nodes):,}; "
            f"settlements low={settlement_pressure['low']:,} "
            f"medium={settlement_pressure['medium']:,} high={settlement_pressure['high']:,}"
        )
    return payload["stats"]  # type: ignore[return-value]


def apply_poi_context_analysis(input_path: str | Path, analysis_path: str | Path, output_path: str | Path, osmium: Any, *, reporter: Any = None) -> dict[str, int]:
    """Apply cached POI context hints to a fresh PBF in one cheap non-spatial pass."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    if source == target:
        raise StageError("POI-context apply input and output must be different files")
    payload = load_poi_context_analysis(analysis_path)
    raw_nodes = payload["nodes"]
    assert isinstance(raw_nodes, dict)
    hints: dict[int, tuple[dict[str, str], dict[str, str]]] = {}
    for raw_id, entry in raw_nodes.items():
        if not isinstance(raw_id, str) or not isinstance(entry, dict):
            continue
        signature = entry.get("signature")
        tags = entry.get("tags")
        if not isinstance(signature, dict) or not isinstance(tags, dict):
            continue
        try:
            node_id = int(raw_id)
        except ValueError:
            continue
        hints[node_id] = (
            {str(key): str(value) for key, value in signature.items()},
            {str(key): str(value) for key, value in tags.items() if str(key) in _CONTEXT_TAGS},
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.poi-context.partial.osm.pbf"
    counters: Counter[str] = Counter()
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)):
                counters["objects_seen"] += 1
                type_method = getattr(item, "type_str", None)
                if not callable(type_method) or type_method() != "node":
                    writer.add(item)
                    continue
                hint = hints.get(int(item.id))
                if hint is None:
                    writer.add(item)
                    continue
                expected_signature, tag_hints = hint
                tags = _tags_dict(item.tags)
                if _signature(tags) != expected_signature:
                    counters["stale_skipped"] += 1
                    writer.add(item)
                    continue
                changed = False
                for key, value in tag_hints.items():
                    if tags.get(key) != value:
                        tags[key] = value
                        changed = True
                if changed:
                    writer.add(item.replace(tags=tags))
                    counters["tagged_nodes"] += 1
                else:
                    writer.add(item)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    result = {
        "objects_seen": counters["objects_seen"],
        "tagged_nodes": counters["tagged_nodes"],
        "stale_skipped": counters["stale_skipped"],
        "analysis_hints": len(hints),
    }
    if reporter is not None:
        reporter(
            f"POI context analysis applied: hints {len(hints):,}; tagged {result['tagged_nodes']:,}; stale skipped {result['stale_skipped']:,}"
        )
    return result

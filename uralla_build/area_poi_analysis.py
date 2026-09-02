"""Reusable artifact for synthetic POIs derived from closed OSM ways."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .area_pois import SyntheticAreaPoi, discover_area_pois
from .errors import StageError


SCHEMA_VERSION = 2
ANALYSIS_KIND = "area_pois"


def _source_metadata(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _candidate_payload(candidate: SyntheticAreaPoi, source_version: int | None) -> dict[str, object]:
    return {
        "source_type": candidate.source_type,
        "source_id": candidate.source_id,
        "source_version": source_version,
        "synthetic_id": candidate.synthetic_id,
        "kind": candidate.kind,
        "lon": candidate.lon,
        "lat": candidate.lat,
        "tags": dict(candidate.tags),
    }


def _source_versions(
    source: Path,
    candidates: list[SyntheticAreaPoi],
    osmium: Any,
) -> dict[int, int]:
    """Read OSM way versions for cached candidates.

    The version is a cheap and conservative freshness guard: if the source way is
    edited in a later Geofabrik extract, the cached synthetic POI is skipped until
    the next ANALYZE.  This pass needs no locations and only runs while rebuilding
    the cache, never on the fast reuse path.
    """
    wanted = {candidate.source_id for candidate in candidates}
    if not wanted:
        return {}
    versions: dict[int, int] = {}
    for item in osmium.FileProcessor(str(source)):
        type_method = getattr(item, "type_str", None)
        kind = type_method() if callable(type_method) else ""
        if kind not in {"way", "w"}:
            continue
        item_id = int(item.id)
        if item_id not in wanted:
            continue
        try:
            versions[item_id] = int(item.version)
        except (AttributeError, TypeError, ValueError):
            versions[item_id] = 0
        if len(versions) == len(wanted):
            break
    return versions


def analyze_area_pois(
    input_path: str | Path,
    output_path: str | Path,
    osmium: Any,
) -> tuple[list[SyntheticAreaPoi], dict[str, int]]:
    """Discover synthetic area POIs once and persist them as a gzip JSON artifact."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"area POI analysis input is missing or empty: {source}")
    candidates = discover_area_pois(str(source), osmium)
    versions = _source_versions(source, candidates, osmium)
    by_kind: dict[str, int] = {}
    for candidate in candidates:
        by_kind[candidate.kind] = by_kind.get(candidate.kind, 0) + 1
    stats: dict[str, int] = {"candidates": len(candidates), "created": len(candidates)}
    for kind, count in sorted(by_kind.items()):
        stats[f"created:{kind}"] = count
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "source": _source_metadata(source),
        "stats": stats,
        "nodes": [
            _candidate_payload(candidate, versions.get(candidate.source_id))
            for candidate in candidates
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.partial"
    try:
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return candidates, stats


def load_area_poi_analysis(path: str | Path) -> dict[str, object]:
    target = Path(path).resolve()
    if not target.is_file() or target.stat().st_size == 0:
        raise StageError(f"area POI artifact is missing or empty: {target}")
    try:
        with gzip.open(target, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StageError(f"cannot read area POI artifact {target}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StageError("area POI artifact must contain a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != ANALYSIS_KIND:
        raise StageError("area POI artifact has an unsupported schema or kind")
    source = payload.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("name"), str):
        raise StageError("area POI artifact has incomplete source metadata")
    if not isinstance(payload.get("nodes"), list):
        raise StageError("area POI artifact is incomplete")
    return payload


def validate_area_poi_analysis(path: str | Path, source: str | Path) -> dict[str, object]:
    """Validate cache scope without requiring byte-identical source input."""
    payload = load_area_poi_analysis(path)
    source_path = Path(source).resolve()
    metadata = payload.get("source")
    assert isinstance(metadata, dict)
    cached_name = str(metadata.get("name") or "")
    if cached_name and cached_name != source_path.name:
        raise StageError(
            f"area POI artifact was built for {cached_name}, not {source_path.name}"
        )
    return payload


def area_poi_candidates_from_analysis(path: str | Path) -> list[SyntheticAreaPoi]:
    return [candidate for candidate, _version in area_poi_reuse_entries_from_analysis(path)]


def area_poi_reuse_entries_from_analysis(
    path: str | Path,
) -> list[tuple[SyntheticAreaPoi, int | None]]:
    """Load cached synthetic nodes together with source-way freshness guards."""
    payload = load_area_poi_analysis(path)
    raw_nodes = payload.get("nodes")
    assert isinstance(raw_nodes, list)
    result: list[tuple[SyntheticAreaPoi, int | None]] = []
    for raw in raw_nodes:
        if not isinstance(raw, Mapping):
            continue
        tags = raw.get("tags")
        if not isinstance(tags, Mapping):
            continue
        try:
            candidate = SyntheticAreaPoi(
                source_type=str(raw.get("source_type", "way")),
                source_id=int(raw["source_id"]),
                kind=str(raw["kind"]),
                lon=float(raw["lon"]),
                lat=float(raw["lat"]),
                tags={str(key): str(value) for key, value in tags.items()},
            )
        except (KeyError, TypeError, ValueError):
            continue
        expected_id = raw.get("synthetic_id")
        if expected_id is not None and int(expected_id) != candidate.synthetic_id:
            raise StageError(
                f"area POI artifact has unstable synthetic ID for way {candidate.source_id}"
            )
        raw_version = raw.get("source_version")
        try:
            source_version = None if raw_version is None else int(raw_version)
        except (TypeError, ValueError):
            source_version = None
        result.append((candidate, source_version))
    result.sort(key=lambda entry: entry[0].source_id)
    return result

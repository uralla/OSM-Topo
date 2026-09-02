"""Reusable artifact for synthetic POIs derived from closed OSM ways."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .area_pois import SyntheticAreaPoi, discover_area_pois
from .errors import StageError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "area_pois"


def _source_identity(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _candidate_payload(candidate: SyntheticAreaPoi) -> dict[str, object]:
    return {
        "source_type": candidate.source_type,
        "source_id": candidate.source_id,
        "synthetic_id": candidate.synthetic_id,
        "kind": candidate.kind,
        "lon": candidate.lon,
        "lat": candidate.lat,
        "tags": dict(candidate.tags),
    }


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
    by_kind: dict[str, int] = {}
    for candidate in candidates:
        by_kind[candidate.kind] = by_kind.get(candidate.kind, 0) + 1
    stats: dict[str, int] = {"candidates": len(candidates), "created": len(candidates)}
    for kind, count in sorted(by_kind.items()):
        stats[f"created:{kind}"] = count
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "source": _source_identity(source),
        "stats": stats,
        "nodes": [_candidate_payload(candidate) for candidate in candidates],
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
    if not isinstance(payload.get("source"), dict) or not isinstance(payload.get("nodes"), list):
        raise StageError("area POI artifact is incomplete")
    return payload


def validate_area_poi_analysis(path: str | Path, source: str | Path) -> dict[str, object]:
    payload = load_area_poi_analysis(path)
    source_path = Path(source).resolve()
    if payload.get("source") != _source_identity(source_path):
        raise StageError("area POI artifact belongs to a different source PBF")
    return payload


def area_poi_candidates_from_analysis(path: str | Path) -> list[SyntheticAreaPoi]:
    payload = load_area_poi_analysis(path)
    raw_nodes = payload.get("nodes")
    assert isinstance(raw_nodes, list)
    result: list[SyntheticAreaPoi] = []
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
        result.append(candidate)
    result.sort(key=lambda candidate: candidate.source_id)
    return result

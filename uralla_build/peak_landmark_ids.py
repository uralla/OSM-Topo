"""Exact OSM-object anchors layered on top of the Wikidata peak catalogue."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .preprocessor import PEAK_LANDMARK_TAG, PEAK_NATURAL_TYPES, enrich_peak_landmark_tags


def load_peak_landmark_node_ids(path: str | Path) -> frozenset[int]:
    """Load optional ``node/<id>`` references from column four of the peak catalogue."""
    source = Path(path)
    node_ids: set[int] = set()
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw_line.split("\t")
        if len(parts) < 4:
            continue
        osm_ref = parts[3].strip()
        if not osm_ref.startswith("node/"):
            continue
        try:
            node_ids.add(int(osm_ref.removeprefix("node/")))
        except ValueError:
            continue
    return frozenset(node_ids)


def enrich_peak_landmark_item(
    item: object,
    tags: Mapping[str, str] | object,
    qids: frozenset[str],
    node_ids: frozenset[int],
) -> tuple[dict[str, str], bool]:
    """Mark a landmark by Wikidata or an explicitly catalogued OSM node id."""
    result, changed = enrich_peak_landmark_tags(tags, qids)
    if changed or result.get(PEAK_LANDMARK_TAG) == "yes":
        return result, changed
    if result.get("natural") not in PEAK_NATURAL_TYPES:
        return result, False

    type_method = getattr(item, "type_str", None)
    object_type = type_method() if callable(type_method) else ""
    if object_type not in {"n", "node"}:
        return result, False
    try:
        object_id = int(getattr(item, "id"))
    except (AttributeError, TypeError, ValueError):
        return result, False
    if object_id not in node_ids:
        return result, False

    result[PEAK_LANDMARK_TAG] = "yes"
    return result, True

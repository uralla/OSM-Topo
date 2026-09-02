"""Cheap semantic/tag pass used after reusable spatial analysis has been applied."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import time
from typing import Any, Sequence
from uuid import uuid4

from .errors import StageError
from .kite import enrich_kite_tags
from .preprocessor import (
    DEFAULT_PEAK_CATALOG,
    DISPLAY_LABEL_TAG,
    PROGRESS_EVERY_OBJECTS,
    _emit_geographic_label_change,
    _object_kind,
    _progress,
    enrich_geographic_label_tags,
    enrich_long_name_tags,
    enrich_peak_landmark_tags,
    enrich_place_admin_tags,
    filter_tags,
    load_blacklist_rules,
    load_peak_landmarks,
)
from .river_landmarks import DEFAULT_RIVER_CATALOG, enrich_river_landmark_tags, load_river_landmarks


def apply_semantic_tags(
    input_path: str | Path,
    output_path: str | Path,
    config_path: str | Path,
    profile_names: Sequence[str],
    report_path: str | Path,
    osmium: Any,
    *,
    peak_catalog_path: str | Path = DEFAULT_PEAK_CATALOG,
    river_catalog_path: str | Path = DEFAULT_RIVER_CATALOG,
) -> dict[str, object]:
    """Apply non-spatial semantic transforms in one streaming PBF pass."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    report_target = Path(report_path).resolve()
    if source == target:
        raise StageError("semantic apply input and output must be different files")
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"semantic input is missing or empty: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    rules = load_blacklist_rules(config_path, profile_names)
    peak_landmarks = load_peak_landmarks(peak_catalog_path)
    river_landmarks = load_river_landmarks(river_catalog_path)
    temporary = target.parent / f".{target.name}.{uuid4().hex}.semantic-lite.partial.osm.pbf"
    counters: Counter[str] = Counter()
    rule_hits: Counter[str] = Counter()
    samples: list[dict[str, object]] = []
    label_samples: list[dict[str, object]] = []
    started = time.monotonic()
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)):
                counters["objects_seen"] += 1
                if counters["objects_seen"] % PROGRESS_EVERY_OBJECTS == 0:
                    _progress(counters["objects_seen"], started)
                decision = filter_tags(item.tags, rules)
                if decision.action != "none":
                    counters[f"{decision.action}_objects"] += 1
                    counters["tags_removed"] += len(decision.removed_keys)
                    rule_hits.update(decision.matched_rules)
                    if len(samples) < 100:
                        samples.append({
                            "type": _object_kind(item),
                            "id": int(item.id),
                            "action": decision.action,
                            "removed_keys": list(decision.removed_keys),
                            "rules": list(decision.matched_rules),
                        })
                final_tags, changed = enrich_place_admin_tags(decision.tags)
                if changed:
                    counters["place_admin_enriched"] += 1
                final_tags, changed = enrich_long_name_tags(final_tags)
                if changed:
                    counters["long_name_enriched"] += 1
                final_tags, changed = enrich_kite_tags(final_tags)
                if changed:
                    counters["kite_infrastructure_enriched"] += 1
                final_tags, changed = enrich_peak_landmark_tags(final_tags, peak_landmarks)
                if changed:
                    counters["peak_landmarks_enriched"] += 1
                before_label = final_tags.get(DISPLAY_LABEL_TAG)
                final_tags, changed = enrich_geographic_label_tags(final_tags)
                if changed or before_label != final_tags.get(DISPLAY_LABEL_TAG):
                    counters["geographic_labels_enriched"] += 1
                    _emit_geographic_label_change(item, final_tags)
                    if len(label_samples) < 100:
                        label_samples.append({
                            "type": _object_kind(item),
                            "id": int(item.id),
                            "name": final_tags.get("name"),
                            "label": final_tags.get(DISPLAY_LABEL_TAG),
                        })
                final_tags, changed = enrich_river_landmark_tags(final_tags, river_landmarks)
                if changed:
                    counters["river_landmarks_enriched"] += 1
                original_tags = {str(key): str(value) for key, value in item.tags}
                writer.add(item if final_tags == original_tags else item.replace(tags=final_tags))
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    elapsed = time.monotonic() - started
    report: dict[str, object] = {
        "schema_version": 1,
        "mode": "semantic-lite",
        "input": str(source),
        "output": str(target),
        "seconds": round(elapsed, 3),
        "counters": dict(counters),
        "rule_hits": dict(rule_hits),
        "samples": samples,
        "geographic_label_samples": label_samples,
    }
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _progress(counters["objects_seen"], started)
    return report

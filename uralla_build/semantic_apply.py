"""Cheap semantic/tag transforms reusable by standalone or unified APPLY passes."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence
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


class SemanticTransformer:
    """Stateful non-spatial tag transformer suitable for an existing writer pass."""

    def __init__(
        self,
        config_path: str | Path,
        profile_names: Sequence[str],
        *,
        peak_catalog_path: str | Path = DEFAULT_PEAK_CATALOG,
        river_catalog_path: str | Path = DEFAULT_RIVER_CATALOG,
    ) -> None:
        self.rules = load_blacklist_rules(config_path, profile_names)
        self.peak_landmarks = load_peak_landmarks(peak_catalog_path)
        self.river_landmarks = load_river_landmarks(river_catalog_path)
        self.counters: Counter[str] = Counter()
        self.rule_hits: Counter[str] = Counter()
        self.samples: list[dict[str, object]] = []
        self.label_samples: list[dict[str, object]] = []
        self.started = time.monotonic()

    def transform(self, item: object, tags: Mapping[str, str]) -> dict[str, str]:
        self.counters["objects_seen"] += 1
        if self.counters["objects_seen"] % PROGRESS_EVERY_OBJECTS == 0:
            _progress(self.counters["objects_seen"], self.started)

        decision = filter_tags(tags, self.rules)
        if decision.action != "none":
            self.counters[f"{decision.action}_objects"] += 1
            self.counters["tags_removed"] += len(decision.removed_keys)
            self.rule_hits.update(decision.matched_rules)
            if len(self.samples) < 100:
                self.samples.append({
                    "type": _object_kind(item),
                    "id": int(getattr(item, "id")),
                    "action": decision.action,
                    "removed_keys": list(decision.removed_keys),
                    "rules": list(decision.matched_rules),
                })

        final_tags, changed = enrich_place_admin_tags(decision.tags)
        if changed:
            self.counters["place_admin_enriched"] += 1
        final_tags, changed = enrich_long_name_tags(final_tags)
        if changed:
            self.counters["long_name_enriched"] += 1
        final_tags, changed = enrich_kite_tags(final_tags)
        if changed:
            self.counters["kite_infrastructure_enriched"] += 1
        final_tags, changed = enrich_peak_landmark_tags(final_tags, self.peak_landmarks)
        if changed:
            self.counters["peak_landmarks_enriched"] += 1
        before_label = final_tags.get(DISPLAY_LABEL_TAG)
        final_tags, changed = enrich_geographic_label_tags(final_tags)
        if changed or before_label != final_tags.get(DISPLAY_LABEL_TAG):
            self.counters["geographic_labels_enriched"] += 1
            _emit_geographic_label_change(item, final_tags)
            if len(self.label_samples) < 100:
                self.label_samples.append({
                    "type": _object_kind(item),
                    "id": int(getattr(item, "id")),
                    "name": final_tags.get("name"),
                    "label": final_tags.get(DISPLAY_LABEL_TAG),
                })
        final_tags, changed = enrich_river_landmark_tags(final_tags, self.river_landmarks)
        if changed:
            self.counters["river_landmarks_enriched"] += 1
        return final_tags

    def report(self, *, input_path: str | Path, output_path: str | Path) -> dict[str, object]:
        return {
            "schema_version": 2,
            "mode": "semantic-lite",
            "input": str(Path(input_path).resolve()),
            "output": str(Path(output_path).resolve()),
            "seconds": round(time.monotonic() - self.started, 3),
            "counters": dict(self.counters),
            "rule_hits": dict(self.rule_hits),
            "samples": self.samples,
            "geographic_label_samples": self.label_samples,
        }


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
    """Apply non-spatial semantic transforms in one standalone streaming PBF pass."""
    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    report_target = Path(report_path).resolve()
    if source == target:
        raise StageError("semantic apply input and output must be different files")
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"semantic input is missing or empty: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    transformer = SemanticTransformer(
        config_path,
        profile_names,
        peak_catalog_path=peak_catalog_path,
        river_catalog_path=river_catalog_path,
    )
    temporary = target.parent / f".{target.name}.{uuid4().hex}.semantic-lite.partial.osm.pbf"
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)):
                original_tags = {str(key): str(value) for key, value in item.tags}
                final_tags = transformer.transform(item, original_tags)
                writer.add(item if final_tags == original_tags else item.replace(tags=final_tags))
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    report = transformer.report(input_path=source, output_path=target)
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _progress(transformer.counters["objects_seen"], transformer.started)
    return report

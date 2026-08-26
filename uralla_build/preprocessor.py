"""Streaming semantic preprocessing, tag blacklists, and static landmark enrichment."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Mapping, Sequence
import unicodedata
from uuid import uuid4

import yaml

from .errors import StageError
from .river_landmarks import (
    DEFAULT_RIVER_CATALOG,
    enrich_river_landmark_tags,
    load_river_landmarks,
)


STRONG_WIKIDATA_KEYS = {
    "wikidata",
    "brand:wikidata",
    "operator:wikidata",
    "political_party:wikidata",
}
POLITICAL_OFFICES = {"political party", "politician"}
WIKIDATA_RE = re.compile(r"\bQ[1-9][0-9]*\b", re.IGNORECASE)
PEAK_LANDMARK_TAG = "uralla:peak_landmark"
PEAK_NATURAL_TYPES = {"peak", "volcano"}
DEFAULT_PEAK_CATALOG = Path(__file__).resolve().parents[1] / "catalog/peak-landmarks.tsv"
PROGRESS_EVERY_OBJECTS = 1_000_000


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized, flags=re.IGNORECASE)
    return " ".join(normalized.split())


@dataclass(frozen=True, slots=True)
class BlacklistRule:
    rule_id: str
    wikidata: frozenset[str]
    exact_aliases: frozenset[str]
    text_patterns: tuple[re.Pattern[str], ...]
    domain_patterns: tuple[re.Pattern[str], ...]

    def matches_text(self, value: str) -> bool:
        normalized = normalize_text(value)
        if normalized in self.exact_aliases:
            return True
        if any(pattern.search(normalized) for pattern in self.text_patterns):
            return True
        raw = unicodedata.normalize("NFKC", value).casefold()
        return any(pattern.search(raw) for pattern in self.domain_patterns)

    def matches_wikidata(self, value: str) -> bool:
        return bool(
            {match.upper() for match in WIKIDATA_RE.findall(value)} & self.wikidata
        )


@dataclass(frozen=True, slots=True)
class FilterDecision:
    tags: dict[str, str]
    action: str
    removed_keys: tuple[str, ...]
    matched_rules: tuple[str, ...]


def _list_of_text(value: object, location: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise StageError(f"{location} must be a list of non-empty strings")
    return list(value)


def load_blacklist_rules(
    path: str | Path, profile_names: Sequence[str]
) -> tuple[BlacklistRule, ...]:
    if not profile_names:
        return ()
    config_path = Path(path)
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise StageError(f"cannot load blacklist {config_path}: {exc}") from exc
    if not isinstance(data, Mapping) or data.get("schema_version") != 1:
        raise StageError("blacklist must be a mapping with schema_version: 1")
    raw_rules = data.get("rules")
    profiles = data.get("profiles")
    if not isinstance(raw_rules, Mapping) or not isinstance(profiles, Mapping):
        raise StageError("blacklist rules/profiles must be mappings")

    selected: list[str] = []
    for profile_name in profile_names:
        profile = profiles.get(profile_name)
        if not isinstance(profile, Mapping):
            raise StageError(f"unknown blacklist profile: {profile_name}")
        for rule_id in _list_of_text(
            profile.get("rules"), f"profiles.{profile_name}.rules"
        ):
            if rule_id not in selected:
                selected.append(rule_id)

    result: list[BlacklistRule] = []
    for rule_id in selected:
        raw = raw_rules.get(rule_id)
        if not isinstance(raw, Mapping):
            raise StageError(f"unknown blacklist rule: {rule_id}")
        wikidata = {
            item.upper()
            for item in _list_of_text(raw.get("wikidata", []), f"rules.{rule_id}.wikidata")
        }
        if any(not re.fullmatch(r"Q[1-9][0-9]*", item) for item in wikidata):
            raise StageError(f"rules.{rule_id}.wikidata contains an invalid entity ID")
        aliases = frozenset(
            normalize_text(item)
            for item in _list_of_text(
                raw.get("exact_aliases", []), f"rules.{rule_id}.exact_aliases"
            )
        )
        try:
            text_patterns = tuple(
                re.compile(pattern, re.IGNORECASE)
                for pattern in _list_of_text(
                    raw.get("text_patterns", []), f"rules.{rule_id}.text_patterns"
                )
            )
        except re.error as exc:
            raise StageError(f"rules.{rule_id}.text_patterns: {exc}") from exc
        domains = _list_of_text(raw.get("domains", []), f"rules.{rule_id}.domains")
        domain_patterns = tuple(
            re.compile(
                rf"(?<![0-9a-z-]){re.escape(domain.casefold())}(?=$|[/:?#.\s])"
            )
            for domain in domains
        )
        result.append(
            BlacklistRule(
                rule_id,
                frozenset(wikidata),
                aliases,
                text_patterns,
                domain_patterns,
            )
        )
    return tuple(result)


def load_peak_landmarks(path: str | Path = DEFAULT_PEAK_CATALOG) -> frozenset[str]:
    """Load a manually maintained TSV catalogue and return its Wikidata QIDs."""

    catalog_path = Path(path)
    try:
        lines = catalog_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise StageError(f"cannot load peak landmark catalogue {catalog_path}: {exc}") from exc

    qids: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        qid = fields[0].strip().upper()
        if qid.casefold() == "qid":
            continue
        if not re.fullmatch(r"Q[1-9][0-9]*", qid):
            raise StageError(
                f"peak landmark catalogue {catalog_path}:{line_number} has invalid QID {qid!r}"
            )
        if qid in qids:
            raise StageError(
                f"peak landmark catalogue {catalog_path}:{line_number} duplicates {qid}"
            )
        qids.add(qid)
    return frozenset(qids)


def enrich_peak_landmark_tags(
    tags: Mapping[str, str] | object,
    landmarks: frozenset[str],
) -> tuple[dict[str, str], bool]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if result.get("natural") not in PEAK_NATURAL_TYPES:
        return result, False
    qids = {match.upper() for match in WIKIDATA_RE.findall(result.get("wikidata", ""))}
    if not qids.intersection(landmarks):
        return result, False
    changed = result.get(PEAK_LANDMARK_TAG) != "yes"
    result[PEAK_LANDMARK_TAG] = "yes"
    return result, changed


def filter_tags(
    tags: Mapping[str, str] | object, rules: Sequence[BlacklistRule]
) -> FilterDecision:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    original = {str(key): str(value) for key, value in items}
    matched_by_key: dict[str, set[str]] = {}
    strong_wikidata = False

    for key, value in original.items():
        matched: set[str] = set()
        for rule in rules:
            if rule.matches_text(value):
                matched.add(rule.rule_id)
            if rule.matches_wikidata(value):
                matched.add(rule.rule_id)
                if key in STRONG_WIKIDATA_KEYS:
                    strong_wikidata = True
        if matched:
            matched_by_key[key] = matched

    if not matched_by_key:
        return FilterDecision(original, "none", (), ())

    office = normalize_text(original.get("office", ""))
    political_context = office in POLITICAL_OFFICES or "political_party" in original
    neutralize = strong_wikidata or political_context
    matched_rules = tuple(
        sorted({rule for values in matched_by_key.values() for rule in values})
    )
    if neutralize:
        return FilterDecision({}, "neutralize", tuple(sorted(original)), matched_rules)
    cleaned = {
        key: value for key, value in original.items() if key not in matched_by_key
    }
    return FilterDecision(
        cleaned,
        "scrub",
        tuple(sorted(matched_by_key)),
        matched_rules,
    )


def _load_osmium() -> Any:
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise StageError(
            "Python package 'osmium' is required for PBF preprocessing; "
            "install the project dependencies"
        ) from exc
    return osmium


def _object_kind(item: object) -> str:
    method = getattr(item, "type_str", None)
    return str(method()) if callable(method) else type(item).__name__.lower()


def _progress(objects_seen: int, started: float) -> None:
    elapsed = max(time.monotonic() - started, 0.001)
    rate = objects_seen / elapsed
    print(
        f"[preprocess] {objects_seen:,} objects; {elapsed:.0f}s; {rate:,.0f} obj/s",
        file=sys.stderr,
        flush=True,
    )


def preprocess_pbf(
    input_path: str | Path,
    output_path: str | Path,
    config_path: str | Path,
    profile_names: Sequence[str],
    report_path: str | Path,
    peak_catalog_path: str | Path = DEFAULT_PEAK_CATALOG,
    river_catalog_path: str | Path = DEFAULT_RIVER_CATALOG,
) -> dict[str, object]:
    """Filter and enrich one PBF atomically with inline blacklist verification."""

    source = Path(input_path).resolve()
    target = Path(output_path).resolve()
    report_target = Path(report_path).resolve()
    if source == target:
        raise StageError("preprocessor input and output must be different files")
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"preprocessor input is missing or empty: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    rules = load_blacklist_rules(config_path, profile_names)
    peak_landmarks = load_peak_landmarks(peak_catalog_path)
    river_landmarks = load_river_landmarks(river_catalog_path)
    osmium = _load_osmium()
    temporary = target.parent / f".{target.name}.{uuid4().hex}.partial.osm.pbf"
    report_temporary = report_target.parent / f".{report_target.name}.{uuid4().hex}.partial"
    counters: Counter[str] = Counter()
    rule_hits: Counter[str] = Counter()
    samples: list[dict[str, object]] = []
    peak_samples: list[dict[str, object]] = []
    river_samples: list[dict[str, object]] = []
    started = time.monotonic()
    print(
        f"[preprocess] start: {source.name} ({source.stat().st_size / (1024 ** 2):.1f} MiB)",
        file=sys.stderr,
        flush=True,
    )
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
                        samples.append(
                            {
                                "type": _object_kind(item),
                                "id": int(item.id),
                                "action": decision.action,
                                "removed_keys": list(decision.removed_keys),
                                "rules": list(decision.matched_rules),
                            }
                        )

                final_tags, peak_added = enrich_peak_landmark_tags(
                    decision.tags, peak_landmarks
                )
                if peak_added:
                    counters["peak_landmarks_enriched"] += 1
                    if len(peak_samples) < 100:
                        peak_samples.append(
                            {
                                "type": _object_kind(item),
                                "id": int(item.id),
                                "wikidata": final_tags.get("wikidata"),
                                "name": final_tags.get("name") or final_tags.get("name:ru"),
                            }
                        )

                final_tags, river_added = enrich_river_landmark_tags(
                    final_tags, river_landmarks
                )
                if river_added:
                    counters["river_landmarks_enriched"] += 1
                    if len(river_samples) < 100:
                        river_samples.append(
                            {
                                "type": _object_kind(item),
                                "id": int(item.id),
                                "rank": final_tags.get("uralla:river_rank"),
                                "name": final_tags.get("name") or final_tags.get("name:ru"),
                            }
                        )

                # The original object was already fully checked above. Re-check only
                # objects whose blacklist decision changed tags; this preserves the
                # blacklist invariant without reading the entire written PBF twice.
                if decision.action != "none":
                    verification = filter_tags(final_tags, rules)
                    if verification.action != "none":
                        raise StageError(
                            f"blacklist verification failed for {_object_kind(item)} {item.id}: "
                            f"{','.join(verification.matched_rules)}"
                        )
                    counters["blacklist_changes_verified"] += 1

                original_tags = {str(key): str(value) for key, value in item.tags}
                if final_tags == original_tags:
                    writer.add(item)
                else:
                    writer.add(item.replace(tags=final_tags))

        _progress(counters["objects_seen"], started)
        report: dict[str, object] = {
            "schema_version": 4,
            "input": str(source),
            "output": str(target),
            "profiles": list(profile_names),
            "rules": [rule.rule_id for rule in rules],
            "peak_catalog": str(Path(peak_catalog_path).resolve()),
            "peak_catalog_entries": len(peak_landmarks),
            "river_catalog": str(Path(river_catalog_path).resolve()),
            "river_catalog_names": len(river_landmarks),
            "objects_seen": counters["objects_seen"],
            "neutralized_objects": counters["neutralize_objects"],
            "scrubbed_objects": counters["scrub_objects"],
            "tags_removed": counters["tags_removed"],
            "peak_landmarks_enriched": counters["peak_landmarks_enriched"],
            "river_landmarks_enriched": counters["river_landmarks_enriched"],
            "rule_hits": dict(sorted(rule_hits.items())),
            "verification_mode": "inline-changed-objects",
            "blacklist_changes_verified": counters["blacklist_changes_verified"],
            "verified_forbidden_tags": 0,
            "samples": samples,
            "peak_landmark_samples": peak_samples,
            "river_landmark_samples": river_samples,
        }
        report_temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
        os.replace(report_temporary, report_target)
        return report
    finally:
        temporary.unlink(missing_ok=True)
        report_temporary.unlink(missing_ok=True)

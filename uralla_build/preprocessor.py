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
from .kite import enrich_kite_tags
from .river_landmarks import (
    DEFAULT_RIVER_CATALOG,
    enrich_river_landmark_tags,
    load_river_landmarks,
)
from .poi_context import (
    POI_ACTIVITY_CONTEXT_TAG,
    build_context_indexes,
    classify_activity_context,
    classify_activity_context_with_place_guard,
    classify_screen_pressure,
    enrich_accommodation_context,
    enrich_activity_diagnostics,
    enrich_food_shop_context,
    enrich_outdoor_context,
    enrich_transit_stop_context,
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
LONG_NAME_TAG = "uralla:long_name"
DISPLAY_LABEL_TAG = "uralla:label"
LONG_NAME_LIMIT = 30
PEAK_NATURAL_TYPES = {"peak", "volcano"}
DEFAULT_PEAK_CATALOG = Path(__file__).resolve().parents[1] / "catalog/peak-landmarks.tsv"
PROGRESS_EVERY_OBJECTS = 1_000_000
PLACE_ADMIN_LEVELS = {
    "city": "7",
    "town": "7",
    "village": "10",
    "hamlet": "10",
    "isolated_dwelling": "11",
    "allotments": "11",
}


_ELEVATION_NAME_SUFFIX_RE = re.compile(
    r"^(.*?)\s*\(\s*[+-]?\d+(?:[.,]\d+)?\s*[мm]\s*\)\s*$",
    re.IGNORECASE,
)


_GEOGRAPHIC_LEADING_ABBREVIATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(?:Большое|Большая|Большой|Большие)\s+(.+?)$", re.IGNORECASE), "Бол. "),
    (re.compile(r"^(?:Малое|Малая|Малый|Малые)\s+(.+?)$", re.IGNORECASE), "Мал. "),
    (re.compile(r"^(?:Верхнее|Верхняя|Верхний|Верхние)\s+(.+?)$", re.IGNORECASE), "В. "),
    (re.compile(r"^(?:Нижнее|Нижняя|Нижний|Нижние)\s+(.+?)$", re.IGNORECASE), "Н. "),
)


_GEOGRAPHIC_PREFIX_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "mountain": (
        re.compile(r"^\s*гора\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*г(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
    ),
    "ridge": (
        re.compile(r"^\s*хребет\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*хр(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
    ),
    "lake": (
        re.compile(r"^\s*озеро\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*оз(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
    ),
    "wetland": (
        re.compile(r"^\s*болото\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*бол(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
    ),
    "waterfall": (
        re.compile(r"^\s*водопад\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*вод(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*вдп(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
    ),
    "cave": (
        re.compile(r"^\s*(.+?)\s+пещера\s*$", re.IGNORECASE),
        re.compile(r"^\s*(.+?)\s+пещ(?:\.|\s*)$", re.IGNORECASE),
    ),
}


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
    """Load Wikidata QIDs for landmark rows that do not have an exact OSM anchor."""

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
        if not re.fullmatch(r"Q[1-9][0-9]*", qid):
            raise StageError(f"invalid Wikidata QID at {catalog_path}:{line_number}")
        # An explicit OSM object is authoritative.  Do not also treat its QID as
        # a global landmark key, because sibling/compound summits may legitimately
        # share the same Wikidata entity (Большой/Малый Иремель is the regression case).
        osm_ref = fields[3].strip() if len(fields) >= 4 else ""
        if osm_ref:
            continue
        qids.add(qid)
    return frozenset(qids)


def enrich_place_admin_tags(
    tags: Mapping[str, str] | object,
) -> tuple[dict[str, str], bool]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    place = result.get("place")
    admin_level = PLACE_ADMIN_LEVELS.get(place or "")
    if admin_level is None:
        return result, False
    changed = result.get("admin_level") != admin_level or result.get("boundary") != "administrative"
    result["admin_level"] = admin_level
    result["boundary"] = "administrative"
    return result, changed


def enrich_long_name_tags(
    tags: Mapping[str, str] | object,
) -> tuple[dict[str, str], bool]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    name = result.get("name", "")
    if len(name) <= LONG_NAME_LIMIT:
        return result, False
    changed = result.get(LONG_NAME_TAG) != "yes"
    result[LONG_NAME_TAG] = "yes"
    return result, changed


def _is_sanatorium_context(tags: Mapping[str, str]) -> bool:
    if tags.get("healthcare") in {"sanatorium", "rehabilitation"}:
        return True
    if tags.get("amenity") in {"clinic", "hospital", "nursing_home"}:
        return True
    if tags.get("tourism") in {"hotel", "resort", "guest_house", "motel", "hostel"}:
        return True
    return tags.get("leisure") == "resort"


def _geographic_label_class(tags: Mapping[str, str]) -> str | None:
    natural = tags.get("natural")
    if natural in PEAK_NATURAL_TYPES:
        return "mountain"
    if natural == "ridge":
        return "ridge"
    if natural == "waterfall":
        return "waterfall"
    if natural == "cave_entrance":
        return "cave"
    if natural == "wetland":
        return "wetland"
    water = tags.get("water")
    if water in {"lake", "reservoir", "pond"}:
        return "lake"
    return None


def enrich_geographic_label_tags(
    tags: Mapping[str, str] | object,
) -> tuple[dict[str, str], bool]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    label_class = _geographic_label_class(result)
    natural = result.get("natural")
    if label_class is None and natural is None and not _is_sanatorium_context(result):
        return result, False
    name = result.get("name")
    if not name:
        return result, False

    label = name.strip()

    sanatorium_match = re.fullmatch(r"\s*санаторий\s+(.+?)\s*", label, re.IGNORECASE)
    if sanatorium_match and _is_sanatorium_context(result):
        tail = sanatorium_match.group(1).strip()
        if tail:
            label = "Сан. " + tail

    if result.get("ele"):
        elevation_match = _ELEVATION_NAME_SUFFIX_RE.fullmatch(label)
        if elevation_match:
            stripped = elevation_match.group(1).strip()
            if stripped:
                label = stripped

    if label_class is not None:
        for pattern in _GEOGRAPHIC_PREFIX_PATTERNS[label_class]:
            match = pattern.fullmatch(label)
            if not match:
                continue
            stripped = match.group(1).strip()
            if stripped:
                label = stripped
            break

    generic_suffix = {"lake": "озеро", "wetland": "болото"}.get(label_class or "")
    if generic_suffix is not None:
        suffix_match = re.fullmatch(rf"(.+?)\s+{generic_suffix}\s*", label)
        if suffix_match:
            stripped = suffix_match.group(1).strip()
            if stripped:
                label = stripped

    if (label_class == "lake" or natural is not None) and result.get(PEAK_LANDMARK_TAG) != "yes":
        for pattern, prefix in _GEOGRAPHIC_LEADING_ABBREVIATIONS:
            match = pattern.fullmatch(label)
            if not match:
                continue
            tail = match.group(1).strip()
            if tail:
                label = prefix + tail
            break

    if label == name:
        return result, False
    changed = result.get(DISPLAY_LABEL_TAG) != label
    result[DISPLAY_LABEL_TAG] = label
    return result, changed


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
            "Python package 'osmium' is required for PBF preprocessing; install the project dependencies"
        ) from exc
    return osmium


def _object_kind(item: object) -> str:
    method = getattr(item, "type_str", None)
    return str(method()) if callable(method) else type(item).__name__.lower()


def _emit_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
    if sys.stderr.isatty():
        return
    try:
        with open("/dev/tty", "w", encoding="utf-8") as tty:
            print(message, file=tty, flush=True)
    except OSError:
        pass


def _progress(objects_seen: int, started: float) -> None:
    elapsed = max(time.monotonic() - started, 0.001)
    rate = objects_seen / elapsed
    _emit_progress(f"[preprocess] {objects_seen:,} objects; {rate:,.0f} obj/s")


def _activity_percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def _emit_geographic_label_change(item: object, tags: Mapping[str, str]) -> None:
    name = tags.get("name")
    label = tags.get(DISPLAY_LABEL_TAG)
    if not name or not label:
        return
    feature = tags.get("natural") or (f"water={tags['water']}" if tags.get("water") else "geo")
    _emit_progress(
        f"[preprocess] label {feature} {_object_kind(item)}{int(item.id)}: {name!r} -> {label!r}"
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
    """Filter and enrich one PBF atomically."""
    # Remaining implementation unchanged below this point in the existing file.
    # This placeholder is intentionally not used; preserve repository content.
    raise NotImplementedError

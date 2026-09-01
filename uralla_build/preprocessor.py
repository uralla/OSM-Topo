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
    "waterfall": (
        re.compile(r"^\s*водопад\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*вод(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*вдп(?:\.\s*|\s+)(.+?)\s*$", re.IGNORECASE),
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
        if not re.fullmatch(r"Q[1-9][0-9]*", qid):
            raise StageError(f"invalid Wikidata QID at {catalog_path}:{line_number}")
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


def _geographic_label_class(tags: Mapping[str, str]) -> str | None:
    natural = tags.get("natural")
    if natural in PEAK_NATURAL_TYPES:
        return "mountain"
    if natural == "ridge":
        return "ridge"
    if natural == "waterfall":
        return "waterfall"
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
    if label_class is None and natural is None:
        return result, False
    name = result.get("name")
    if not name:
        return result, False

    label = name.strip()
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

    # Compact directional/size adjectives on ordinary natural features and lakes.
    # Prominent peak/volcano landmarks keep their full display names.
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
            "Python package 'osmium' is required for PBF preprocessing; "
            "install the project dependencies"
        ) from exc
    return osmium


def _object_kind(item: object) -> str:
    method = getattr(item, "type_str", None)
    return str(method()) if callable(method) else type(item).__name__.lower()


def _emit_progress(message: str) -> None:
    """Persist progress to stderr and mirror it to an attached controlling TTY."""

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
        f"[preprocess] label {feature} {_object_kind(item)}{int(item.id)}: "
        f"{name!r} -> {label!r}"
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
    _emit_progress("POI context: indexing node signals in one pass")
    context_started = time.monotonic()
    context_indexes = build_context_indexes(str(source), osmium)
    food_shop_index = context_indexes.food
    accommodation_index = context_indexes.accommodation
    transit_stop_index = context_indexes.transit
    picnic_index = context_indexes.picnic
    outdoor_furniture_index = context_indexes.outdoor_furniture
    tourist_retail_index = context_indexes.tourist_retail
    spring_index = context_indexes.spring
    activity_index = context_indexes.activity
    screen_pressure_index = context_indexes.screen_pressure
    place_anchor_index = context_indexes.places

    # Percentile thresholds must be known before the writer pass so the final
    # activity context can be persisted for mkgmap without a third PBF scan.
    candidate_activity_500m: list[int] = []
    candidate_activity_2km: list[int] = []
    candidate_activity_10km: list[int] = []
    for _candidate_id, candidate_lat, candidate_lon in context_indexes.adaptive_candidates:
        candidate_activity_500m.append(activity_index.count_within(candidate_lat, candidate_lon, 0.5))
        candidate_activity_2km.append(activity_index.count_within(candidate_lat, candidate_lon, 2.0))
        candidate_activity_10km.append(activity_index.count_cells_within_circle(candidate_lat, candidate_lon, 10.0))
    activity_thresholds = {
        "2km_p25": _activity_percentile(candidate_activity_2km, 0.25),
        "2km_p75": _activity_percentile(candidate_activity_2km, 0.75),
        "10km_p25": _activity_percentile(candidate_activity_10km, 0.25),
        "10km_p75": _activity_percentile(candidate_activity_10km, 0.75),
    }
    candidate_screen_2km: list[int] = []
    candidate_screen_10km: list[int] = []
    for _candidate_id, candidate_lat, candidate_lon in context_indexes.adaptive_candidates:
        candidate_screen_2km.append(screen_pressure_index.score_within(candidate_lat, candidate_lon, 2.0))
        candidate_screen_10km.append(screen_pressure_index.score_cells_within_circle(candidate_lat, candidate_lon, 10.0))
    screen_thresholds = {
        "2km_p25": _activity_percentile(candidate_screen_2km, 0.25),
        "2km_p75": _activity_percentile(candidate_screen_2km, 0.75),
        "10km_p25": _activity_percentile(candidate_screen_10km, 0.25),
        "10km_p75": _activity_percentile(candidate_screen_10km, 0.75),
    }
    _emit_progress(
        "POI activity thresholds ready before writer; "
        f"samples {len(context_indexes.adaptive_candidates):,}; "
        f"2km p25={activity_thresholds['2km_p25']} p75={activity_thresholds['2km_p75']}; "
        f"10km p25={activity_thresholds['10km_p25']} p75={activity_thresholds['10km_p75']}"
    )
    _emit_progress(
        "POI screen pressure thresholds ready before writer; "
        f"samples {len(context_indexes.adaptive_candidates):,}; "
        f"2km p25={screen_thresholds['2km_p25']} p75={screen_thresholds['2km_p75']}; "
        f"10km p25={screen_thresholds['10km_p25']} p75={screen_thresholds['10km_p75']}"
    )
    _emit_progress(
        "POI context: one-pass index complete; "
        f"food {food_shop_index.shop_count:,}; "
        f"accommodation {accommodation_index.shop_count:,}; "
        f"transit {transit_stop_index.shop_count:,}; "
        f"picnic {picnic_index.shop_count:,}; "
        f"furniture {outdoor_furniture_index.shop_count:,}; "
        f"retail {tourist_retail_index.shop_count:,}; "
        f"spring {spring_index.shop_count:,}; "
        f"activity {activity_index.shop_count:,}; "
        f"screen {screen_pressure_index.point_count:,}/{screen_pressure_index.total_weight:,}w; "
        f"places {place_anchor_index.anchor_count:,}; "
        f"{time.monotonic() - context_started:.1f}s"
    )
    temporary = target.parent / f".{target.name}.{uuid4().hex}.partial.osm.pbf"
    report_temporary = report_target.parent / f".{report_target.name}.{uuid4().hex}.partial"
    counters: Counter[str] = Counter()
    rule_hits: Counter[str] = Counter()
    samples: list[dict[str, object]] = []
    geographic_label_samples: list[dict[str, object]] = []
    peak_samples: list[dict[str, object]] = []
    river_samples: list[dict[str, object]] = []
    poi_context_samples: list[dict[str, object]] = []
    accommodation_context_samples: list[dict[str, object]] = []
    transit_context_samples: list[dict[str, object]] = []
    activity_context_samples: list[dict[str, object]] = []
    activity_500m_values: list[int] = []
    activity_2km_values: list[int] = []
    activity_10km_values: list[int] = []
    solnyshko_accommodation_sample: dict[str, object] | None = None
    started = time.monotonic()
    _emit_progress(
        f"[preprocess] start: {source.name} ({source.stat().st_size / (1024 ** 2):.1f} MiB)"
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

                final_tags, place_admin_added = enrich_place_admin_tags(decision.tags)
                if place_admin_added:
                    counters["place_admin_enriched"] += 1
                final_tags, _long_name_added = enrich_long_name_tags(final_tags)
                final_tags, peak_added = enrich_peak_landmark_tags(
                    final_tags, peak_landmarks
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
                before_label = final_tags.get(DISPLAY_LABEL_TAG)
                final_tags, label_added = enrich_geographic_label_tags(final_tags)
                if label_added:
                    counters["geographic_labels_enriched"] += 1
                    _emit_geographic_label_change(item, final_tags)
                    if len(geographic_label_samples) < 100:
                        geographic_label_samples.append(
                            {
                                "type": _object_kind(item),
                                "id": int(item.id),
                                "name": final_tags.get("name"),
                                "label": final_tags.get(DISPLAY_LABEL_TAG),
                                "natural": final_tags.get("natural"),
                                "water": final_tags.get("water"),
                            }
                        )
                elif before_label != final_tags.get(DISPLAY_LABEL_TAG):
                    counters["geographic_labels_enriched"] += 1

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

                final_tags, poi_context_added, poi_context_sample = enrich_food_shop_context(
                    item, final_tags, food_shop_index
                )
                if poi_context_added:
                    counters["poi_context_enriched"] += 1
                    priority = final_tags.get("uralla:poi_priority", "unknown")
                    counters[f"poi_priority_{priority}"] += 1
                    if poi_context_sample is not None and len(poi_context_samples) < 200:
                        poi_context_samples.append(poi_context_sample)

                final_tags, accommodation_added, accommodation_sample = enrich_accommodation_context(
                    item, final_tags, accommodation_index
                )
                if accommodation_added:
                    counters["accommodation_context_enriched"] += 1
                    accommodation_priority = final_tags.get("uralla:poi_priority", "unknown")
                    counters[f"accommodation_priority_{accommodation_priority}"] += 1
                    if accommodation_sample is not None and len(accommodation_context_samples) < 200:
                        accommodation_context_samples.append(accommodation_sample)
                    if (
                        accommodation_sample is not None
                        and accommodation_sample.get("name") == "Солнышко"
                    ):
                        solnyshko_accommodation_sample = dict(accommodation_sample)
                    if (
                        accommodation_sample is not None
                        and accommodation_sample.get("name")
                        and (
                            accommodation_priority != "common"
                            or normalize_text(str(accommodation_sample.get("name"))) == "солнышко"
                        )
                    ):
                        _emit_progress(
                            "POI accommodation: "
                            f"{accommodation_sample['name']!r}; "
                            f"2km={accommodation_sample['objects_2km']}; "
                            f"10km={accommodation_sample['objects_10km']}; "
                            f"priority={accommodation_priority}"
                        )

                final_tags, transit_added, transit_sample = enrich_transit_stop_context(
                    item, final_tags, transit_stop_index
                )
                if transit_added:
                    counters["transit_context_enriched"] += 1
                    transit_priority = final_tags.get("uralla:poi_priority", "unknown")
                    counters[f"transit_priority_{transit_priority}"] += 1
                    if transit_sample is not None and len(transit_context_samples) < 200:
                        transit_context_samples.append(transit_sample)

                final_tags, picnic_added, _picnic_sample = enrich_outdoor_context(
                    item, final_tags, picnic_index, kind="picnic"
                )
                if picnic_added:
                    counters["picnic_context_enriched"] += 1

                final_tags, furniture_added, _furniture_sample = enrich_outdoor_context(
                    item, final_tags, outdoor_furniture_index, kind="furniture"
                )
                if furniture_added:
                    counters["furniture_context_enriched"] += 1

                final_tags, retail_added, _retail_sample = enrich_outdoor_context(
                    item, final_tags, tourist_retail_index, kind="retail"
                )
                if retail_added:
                    counters["retail_context_enriched"] += 1

                final_tags, spring_added, _spring_sample = enrich_outdoor_context(
                    item, final_tags, spring_index, kind="spring"
                )
                if spring_added:
                    counters["spring_context_enriched"] += 1

                final_tags, activity_added, activity_sample = enrich_activity_diagnostics(
                    item, final_tags, activity_index, place_anchor_index, activity_thresholds, screen_pressure_index, screen_thresholds
                )
                if activity_added:
                    counters["activity_context_enriched"] += 1
                    if activity_sample is not None:
                        activity_500m_values.append(int(activity_sample["activity_500m"]))
                        activity_2km_values.append(int(activity_sample["activity_2km"]))
                        activity_10km_values.append(int(activity_sample["activity_10km"]))
                    if activity_sample is not None:
                        activity_context_samples.append(activity_sample)
                    if (
                        activity_sample is not None
                        and activity_sample.get("name") == "Солнышко"
                        and solnyshko_accommodation_sample is not None
                        and activity_sample.get("id") == solnyshko_accommodation_sample.get("id")
                    ):
                        solnyshko_accommodation_sample["activity_500m"] = activity_sample["activity_500m"]
                        solnyshko_accommodation_sample["activity_2km"] = activity_sample["activity_2km"]
                        solnyshko_accommodation_sample["activity_10km"] = activity_sample["activity_10km"]
                        solnyshko_accommodation_sample["screen_pressure_2km"] = activity_sample["screen_pressure_2km"]
                        solnyshko_accommodation_sample["screen_pressure_10km"] = activity_sample["screen_pressure_10km"]
                        solnyshko_accommodation_sample["screen_pressure"] = activity_sample["screen_pressure"]

                activity_context_value = final_tags.get(POI_ACTIVITY_CONTEXT_TAG)
                if activity_context_value in {"remote", "settlement", "urban"}:
                    counters[f"activity_context_written_{activity_context_value}"] += 1

                lod_class_value = final_tags.get("uralla:poi_lod_class")
                if lod_class_value in {"H", "M", "L"}:
                    counters[f"poi_lod_class_{lod_class_value}"] += 1
                    if int(getattr(item, "id", 0)) == 4912997022:
                        _emit_progress(
                            "POI LOD named check: 'Солнышко' Ai-Petri; "
                            f"id={int(item.id)}; priority={final_tags.get('uralla:poi_priority')}; "
                            f"activity={final_tags.get('uralla:poi_activity_context')}; "
                            f"screen={final_tags.get('uralla:poi_screen_pressure')}; "
                            f"lod={lod_class_value}; "
                            f"screen2km={final_tags.get('uralla:poi_screen_pressure_2km')}; "
                            f"screen10km={final_tags.get('uralla:poi_screen_pressure_10km')}"
                        )

                original_tags = {str(key): str(value) for key, value in item.tags}
                if final_tags == original_tags:
                    writer.add(item)
                else:
                    writer.add(item.replace(tags=final_tags))

        _progress(counters["objects_seen"], started)
        _emit_progress(
            "POI context: "
            f"food shops {counters['poi_context_enriched']:,}; "
            f"common {counters['poi_priority_common']:,}; "
            f"sparse {counters['poi_priority_sparse']:,}; "
            f"isolated {counters['poi_priority_isolated']:,}"
        )
        _emit_progress(
            "POI activity context tags written: "
            f"remote {counters['activity_context_written_remote']:,}; "
            f"settlement {counters['activity_context_written_settlement']:,}; "
            f"urban {counters['activity_context_written_urban']:,}; "
            f"total {sum(counters[f'activity_context_written_{value}'] for value in ('remote', 'settlement', 'urban')):,}"
        )
        _emit_progress(
            "POI final LOD diagnostics: "
            f"H={counters['poi_lod_class_H']:,}; "
            f"M={counters['poi_lod_class_M']:,}; "
            f"L={counters['poi_lod_class_L']:,}; "
            f"total={sum(counters[f'poi_lod_class_{value}'] for value in ('H', 'M', 'L')):,}"
        )
        if candidate_screen_2km:
            screen_counts = Counter(
                classify_screen_pressure(
                    pressure_2km=p2, pressure_10km=p10,
                    local_p25=screen_thresholds["2km_p25"], local_p75=screen_thresholds["2km_p75"],
                    background_p25=screen_thresholds["10km_p25"], background_p75=screen_thresholds["10km_p75"],
                )
                for p2, p10 in zip(candidate_screen_2km, candidate_screen_10km)
            )
            _emit_progress(
                "POI screen pressure: "
                f"samples {len(candidate_screen_2km):,}; "
                f"2km p25={screen_thresholds['2km_p25']} p50={_activity_percentile(candidate_screen_2km, 0.50)} p75={screen_thresholds['2km_p75']} p90={_activity_percentile(candidate_screen_2km, 0.90)}; "
                f"10km p25={screen_thresholds['10km_p25']} p50={_activity_percentile(candidate_screen_10km, 0.50)} p75={screen_thresholds['10km_p75']} p90={_activity_percentile(candidate_screen_10km, 0.90)}; "
                f"low={screen_counts['low']:,}; medium={screen_counts['medium']:,}; high={screen_counts['high']:,}"
            )
            if solnyshko_accommodation_sample is not None:
                _emit_progress(
                    "POI screen pressure named check: 'Солнышко'; "
                    f"id={solnyshko_accommodation_sample.get('id')}; "
                    f"priority={solnyshko_accommodation_sample.get('priority')}; "
                    f"2km={solnyshko_accommodation_sample.get('screen_pressure_2km')}; "
                    f"10km={solnyshko_accommodation_sample.get('screen_pressure_10km')}; "
                    f"pressure={solnyshko_accommodation_sample.get('screen_pressure')}; "
                    f"activity2km={solnyshko_accommodation_sample.get('activity_2km')}; "
                    f"activity10km={solnyshko_accommodation_sample.get('activity_10km')}"
                )

        if activity_500m_values:
            activity_2km_p25 = _activity_percentile(activity_2km_values, 0.25)
            activity_2km_p75 = _activity_percentile(activity_2km_values, 0.75)
            activity_10km_p25 = _activity_percentile(activity_10km_values, 0.25)
            activity_10km_p75 = _activity_percentile(activity_10km_values, 0.75)
            _emit_progress(
                "POI activity density: "
                f"samples {len(activity_500m_values):,}; "
                f"500m p25={_activity_percentile(activity_500m_values, 0.25)} "
                f"p50={_activity_percentile(activity_500m_values, 0.50)} "
                f"p75={_activity_percentile(activity_500m_values, 0.75)} "
                f"p90={_activity_percentile(activity_500m_values, 0.90)}; "
                f"2km p25={_activity_percentile(activity_2km_values, 0.25)} "
                f"p50={_activity_percentile(activity_2km_values, 0.50)} "
                f"p75={_activity_percentile(activity_2km_values, 0.75)} "
                f"p90={_activity_percentile(activity_2km_values, 0.90)}; "
                f"10km p25={_activity_percentile(activity_10km_values, 0.25)} "
                f"p50={_activity_percentile(activity_10km_values, 0.50)} "
                f"p75={_activity_percentile(activity_10km_values, 0.75)} "
                f"p90={_activity_percentile(activity_10km_values, 0.90)}"
            )
            activity_class_counts: Counter[str] = Counter(
                classify_activity_context(
                    activity_2km=activity_2km,
                    activity_10km=activity_10km,
                    local_p25=activity_2km_p25,
                    local_p75=activity_2km_p75,
                    background_p25=activity_10km_p25,
                    background_p75=activity_10km_p75,
                )
                for activity_2km, activity_10km in zip(activity_2km_values, activity_10km_values)
            )
            _emit_progress(
                "POI activity classifier: "
                f"remote {activity_class_counts['remote']:,}; "
                f"settlement {activity_class_counts['settlement']:,}; "
                f"urban {activity_class_counts['urban']:,}; "
                f"criteria remote=(2km<=p25 and 10km<=p25), "
                f"urban=(2km>=p75 and 10km>=p75)"
            )
            guarded_class_counts: Counter[str] = Counter()
            activity_kind_counts: Counter[tuple[str, str]] = Counter()
            edge_samples: dict[tuple[str, str], list[dict[str, object]]] = {}
            for sample in activity_context_samples:
                context = classify_activity_context_with_place_guard(
                    activity_2km=int(sample["activity_2km"]),
                    activity_10km=int(sample["activity_10km"]),
                    local_p25=activity_2km_p25,
                    local_p75=activity_2km_p75,
                    background_p25=activity_10km_p25,
                    background_p75=activity_10km_p75,
                    place_by_type=sample.get("place_by_type"),
                )
                guarded_class_counts[context] += 1
                kind = str(sample.get("kind") or "other")
                activity_kind_counts[(context, kind)] += 1
                if context in {"remote", "urban"}:
                    bucket = edge_samples.setdefault((context, kind), [])
                    if len(bucket) < 8:
                        bucket.append(sample)

            _emit_progress(
                "POI activity final classifier: "
                f"remote {guarded_class_counts['remote']:,}; "
                f"settlement {guarded_class_counts['settlement']:,}; "
                f"urban {guarded_class_counts['urban']:,}; "
                "place_guard=city:7,town:5,village:2,hamlet:1km"
            )

            for context in ("remote", "settlement", "urban"):
                _emit_progress(
                    "POI activity matrix: "
                    f"context={context}; "
                    f"food={activity_kind_counts[(context, 'food')]:,}; "
                    f"accommodation={activity_kind_counts[(context, 'accommodation')]:,}; "
                    f"transit={activity_kind_counts[(context, 'transit')]:,}; "
                    f"other={activity_kind_counts[(context, 'other')]:,}"
                )

            for sample in activity_context_samples:
                if normalize_text(str(sample.get("name") or "")) != "старый крым":
                    continue
                raw_context = classify_activity_context(
                    activity_2km=int(sample["activity_2km"]),
                    activity_10km=int(sample["activity_10km"]),
                    local_p25=activity_2km_p25,
                    local_p75=activity_2km_p75,
                    background_p25=activity_10km_p25,
                    background_p75=activity_10km_p75,
                )
                final_context = classify_activity_context_with_place_guard(
                    activity_2km=int(sample["activity_2km"]),
                    activity_10km=int(sample["activity_10km"]),
                    local_p25=activity_2km_p25,
                    local_p75=activity_2km_p75,
                    background_p25=activity_10km_p25,
                    background_p75=activity_10km_p75,
                    place_by_type=sample.get("place_by_type"),
                )
                _emit_progress(
                    "POI named check: 'Старый Крым'; "
                    f"id={sample.get('id')}; kind={sample.get('kind')}; raw_context={raw_context}; final_context={final_context}; "
                    f"priority={sample.get('priority')}; 2km={sample.get('activity_2km')}; "
                    f"10km={sample.get('activity_10km')}; place={sample.get('place_name')!r}; "
                    f"place_type={sample.get('place_type')}; "
                    f"place_km={format(float(sample['place_distance_km']), '.2f') if sample.get('place_distance_km') is not None else 'n/a'}; "
                    f"lat={float(sample['lat']):.6f}; lon={float(sample['lon']):.6f}"
                )

            for context in ("remote", "urban"):
                for kind in ("food", "accommodation", "transit", "other"):
                    for sample in edge_samples.get((context, kind), ()):
                        _emit_progress(
                            f"POI activity sample: {context}; "
                            f"id={sample.get('id')}; name={sample.get('name')!r}; "
                            f"kind={sample.get('kind')}; priority={sample.get('priority')}; "
                            f"500m={sample.get('activity_500m')}; 2km={sample.get('activity_2km')}; "
                            f"10km={sample.get('activity_10km')}; place={sample.get('place_name')!r}; "
                            f"place_type={sample.get('place_type')}; "
                            f"place_km={format(float(sample['place_distance_km']), '.2f') if sample.get('place_distance_km') is not None else 'n/a'}"
                        )
        _emit_progress(
            f"POI context: hotels/hostels {accommodation_index.shop_count:,}; "
            f"common {counters['accommodation_priority_common']:,}; "
            f"sparse {counters['accommodation_priority_sparse']:,}; "
            f"isolated {counters['accommodation_priority_isolated']:,}"
        )
        if solnyshko_accommodation_sample is None:
            _emit_progress("POI accommodation check: 'Солнышко' not enriched")
        else:
            _emit_progress(
                "POI accommodation check: "
                f"'Солнышко'; id={solnyshko_accommodation_sample['id']}; "
                f"lat={float(solnyshko_accommodation_sample['lat']):.6f}; "
                f"lon={float(solnyshko_accommodation_sample['lon']):.6f}; "
                f"2km={solnyshko_accommodation_sample['objects_2km']}; "
                f"10km={solnyshko_accommodation_sample['objects_10km']}; "
                f"activity500m={solnyshko_accommodation_sample.get('activity_500m', 'n/a')}; "
                f"activity2km={solnyshko_accommodation_sample.get('activity_2km', 'n/a')}; "
                f"activity10km={solnyshko_accommodation_sample.get('activity_10km', 'n/a')}; "
                f"activity_context={classify_activity_context(activity_2km=int(solnyshko_accommodation_sample.get('activity_2km', 0)), activity_10km=int(solnyshko_accommodation_sample.get('activity_10km', 0)), local_p25=activity_2km_p25, local_p75=activity_2km_p75, background_p25=activity_10km_p25, background_p75=activity_10km_p75) if activity_500m_values else 'n/a'}; "
                f"priority={solnyshko_accommodation_sample['priority']}"
            )
        _emit_progress(
            f"POI context: activity nodes {activity_index.shop_count:,}; "
            f"enriched POIs {counters['activity_context_enriched']:,}"
        )
        _emit_progress(
            f"POI context: transit stops {transit_stop_index.shop_count:,}; "
            f"common {counters['transit_priority_common']:,}; "
            f"sparse {counters['transit_priority_sparse']:,}; "
            f"isolated {counters['transit_priority_isolated']:,}"
        )
        report: dict[str, object] = {
            "schema_version": 8,
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
            "place_admin_enriched": counters["place_admin_enriched"],
            "geographic_labels_enriched": counters["geographic_labels_enriched"],
            "peak_landmarks_enriched": counters["peak_landmarks_enriched"],
            "river_landmarks_enriched": counters["river_landmarks_enriched"],
            "poi_context_index_node_shops": food_shop_index.shop_count,
            "accommodation_context_index_nodes": accommodation_index.shop_count,
            "transit_context_index_nodes": transit_stop_index.shop_count,
            "activity_context_index_nodes": activity_index.shop_count,
            "activity_context_enriched": counters["activity_context_enriched"],
            "poi_lod_class_H": counters["poi_lod_class_H"],
            "poi_lod_class_M": counters["poi_lod_class_M"],
            "poi_lod_class_L": counters["poi_lod_class_L"],
            "transit_context_enriched": counters["transit_context_enriched"],
            "transit_priority_common": counters["transit_priority_common"],
            "transit_priority_sparse": counters["transit_priority_sparse"],
            "transit_priority_isolated": counters["transit_priority_isolated"],
            "accommodation_context_enriched": counters["accommodation_context_enriched"],
            "accommodation_priority_common": counters["accommodation_priority_common"],
            "accommodation_priority_sparse": counters["accommodation_priority_sparse"],
            "accommodation_priority_isolated": counters["accommodation_priority_isolated"],
            "poi_context_enriched": counters["poi_context_enriched"],
            "poi_priority_common": counters["poi_priority_common"],
            "poi_priority_sparse": counters["poi_priority_sparse"],
            "poi_priority_isolated": counters["poi_priority_isolated"],
            "rule_hits": dict(sorted(rule_hits.items())),
            "verification_mode": "disabled",
            "samples": samples,
            "geographic_label_samples": geographic_label_samples,
            "peak_landmark_samples": peak_samples,
            "river_landmark_samples": river_samples,
            "poi_context_samples": poi_context_samples,
            "accommodation_context_samples": accommodation_context_samples,
            "transit_context_samples": transit_context_samples,
            "activity_context_samples": activity_context_samples,
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

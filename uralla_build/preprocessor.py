"""Streaming semantic preprocessing and configurable tag blacklists."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
import unicodedata
from uuid import uuid4

import yaml

from .errors import StageError


STRONG_WIKIDATA_KEYS = {
    "wikidata",
    "brand:wikidata",
    "operator:wikidata",
    "political_party:wikidata",
}
POLITICAL_OFFICES = {"political party", "politician"}
WIKIDATA_RE = re.compile(r"\bQ[1-9][0-9]*\b", re.IGNORECASE)


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
    if not profile_names:
        raise StageError("at least one blacklist profile is required")

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
        return FilterDecision(
            {}, "neutralize", tuple(sorted(original)), matched_rules
        )
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


def _verify_output(path: Path, rules: Sequence[BlacklistRule], osmium: Any) -> int:
    objects = 0
    for item in osmium.FileProcessor(str(path)):
        objects += 1
        decision = filter_tags(item.tags, rules)
        if decision.action != "none":
            raise StageError(
                f"blacklist verification failed for {_object_kind(item)} {item.id}: "
                f"{','.join(decision.matched_rules)}"
            )
    return objects


def preprocess_pbf(
    input_path: str | Path,
    output_path: str | Path,
    config_path: str | Path,
    profile_names: Sequence[str],
    report_path: str | Path,
) -> dict[str, object]:
    """Filter one PBF atomically, then scan the output for forbidden tags."""

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
    osmium = _load_osmium()
    temporary = target.parent / f".{target.name}.{uuid4().hex}.partial.osm.pbf"
    report_temporary = report_target.parent / f".{report_target.name}.{uuid4().hex}.partial"
    counters: Counter[str] = Counter()
    rule_hits: Counter[str] = Counter()
    samples: list[dict[str, object]] = []
    try:
        with osmium.SimpleWriter(str(temporary)) as writer:
            for item in osmium.FileProcessor(str(source)):
                counters["objects_seen"] += 1
                decision = filter_tags(item.tags, rules)
                if decision.action == "none":
                    writer.add(item)
                    continue
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
                writer.add(item.replace(tags=decision.tags))

        verified_objects = _verify_output(temporary, rules, osmium)
        if verified_objects != counters["objects_seen"]:
            raise StageError(
                "blacklist verification object count differs from input: "
                f"{verified_objects} != {counters['objects_seen']}"
            )
        report: dict[str, object] = {
            "schema_version": 1,
            "input": str(source),
            "output": str(target),
            "profiles": list(profile_names),
            "rules": [rule.rule_id for rule in rules],
            "objects_seen": counters["objects_seen"],
            "neutralized_objects": counters["neutralize_objects"],
            "scrubbed_objects": counters["scrub_objects"],
            "tags_removed": counters["tags_removed"],
            "rule_hits": dict(sorted(rule_hits.items())),
            "verified_forbidden_tags": 0,
            "samples": samples,
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

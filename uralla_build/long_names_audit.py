"""Streaming audit of overlong OSM names and recurring shortening candidates."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Iterable, Mapping
import unicodedata

from .errors import StageError


DEFAULT_LIMIT = 30
DEFAULT_TOP = 100
DEFAULT_EXAMPLES = 5
PROGRESS_EVERY_OBJECTS = 1_000_000
WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+(?:[-’'][0-9A-Za-zА-Яа-яЁё]+)*")
STOPWORDS = frozenset(
    {
        "а", "без", "в", "во", "для", "до", "за", "и", "из", "к", "ко", "на",
        "над", "о", "об", "от", "по", "под", "при", "с", "со", "у", "через",
        "the", "of", "and", "in", "on", "to", "for",
    }
)
PRIMARY_KEYS = (
    "highway", "waterway", "railway", "aeroway", "route", "boundary", "place",
    "natural", "landuse", "leisure", "amenity", "tourism", "historic", "shop",
    "man_made", "building", "office", "craft", "sport",
)
LINEAR_KEYS = frozenset({"highway", "waterway", "railway", "aeroway", "route", "boundary"})


def normalize_words(text: str) -> list[str]:
    """Return normalized lexical tokens suitable for frequency counting."""
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return WORD_RE.findall(normalized)


def significant_words(text: str) -> list[str]:
    return [word for word in normalize_words(text) if word not in STOPWORDS and len(word) > 1]


def ngrams(words: list[str], size: int) -> Iterable[str]:
    for index in range(len(words) - size + 1):
        yield " ".join(words[index : index + size])


def length_bucket(length: int) -> str:
    if length <= 40:
        return "31-40"
    if length <= 50:
        return "41-50"
    if length <= 75:
        return "51-75"
    if length <= 100:
        return "76-100"
    return ">100"


def primary_tag(tags: Mapping[str, str]) -> str:
    for key in PRIMARY_KEYS:
        value = tags.get(key)
        if value:
            return f"{key}={value}"
    return "other"


def _object_kind(item: object) -> str:
    method = getattr(item, "type_str", None)
    raw = str(method()) if callable(method) else type(item).__name__.lower()
    return {"n": "node", "w": "way", "r": "relation"}.get(raw, raw)


def _way_geometry(item: object) -> str:
    if _object_kind(item) != "way":
        return "-"
    closed = getattr(item, "is_closed", None)
    try:
        return "closed_way" if callable(closed) and closed() else "open_way"
    except (RuntimeError, TypeError):
        return "way"


def _emit_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


@dataclass(slots=True)
class TermStats:
    occurrences: Counter[str] = field(default_factory=Counter)
    objects: Counter[str] = field(default_factory=Counter)
    examples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, terms: Iterable[str], name: str, example_limit: int) -> None:
        terms_list = list(terms)
        self.occurrences.update(terms_list)
        for term in set(terms_list):
            self.objects[term] += 1
            examples = self.examples[term]
            if name not in examples and len(examples) < example_limit:
                examples.append(name)


@dataclass(slots=True)
class AuditState:
    objects_seen: int = 0
    long_names: int = 0
    by_kind: Counter[str] = field(default_factory=Counter)
    by_geometry: Counter[str] = field(default_factory=Counter)
    by_primary_tag: Counter[str] = field(default_factory=Counter)
    by_length: Counter[str] = field(default_factory=Counter)
    linear_by_tag: Counter[str] = field(default_factory=Counter)
    examples_by_tag: dict[str, list[dict[str, object]]] = field(default_factory=lambda: defaultdict(list))
    words: TermStats = field(default_factory=TermStats)
    bigrams: TermStats = field(default_factory=TermStats)
    trigrams: TermStats = field(default_factory=TermStats)
    highway_words: TermStats = field(default_factory=TermStats)


def add_name_to_state(
    state: AuditState,
    *,
    name: str,
    tags: Mapping[str, str],
    kind: str,
    geometry: str,
    object_id: int,
    limit: int = DEFAULT_LIMIT,
    example_limit: int = DEFAULT_EXAMPLES,
) -> bool:
    """Record one object when its name exceeds the configured limit."""
    if len(name) <= limit:
        return False

    state.long_names += 1
    state.by_kind[kind] += 1
    if geometry != "-":
        state.by_geometry[geometry] += 1
    tag = primary_tag(tags)
    state.by_primary_tag[tag] += 1
    state.by_length[length_bucket(len(name))] += 1

    key = tag.partition("=")[0]
    if key in LINEAR_KEYS:
        state.linear_by_tag[tag] += 1

    examples = state.examples_by_tag[tag]
    if len(examples) < example_limit:
        examples.append({"type": kind, "id": object_id, "length": len(name), "name": name})

    words = significant_words(name)
    state.words.add(words, name, example_limit)
    state.bigrams.add(ngrams(words, 2), name, example_limit)
    state.trigrams.add(ngrams(words, 3), name, example_limit)
    if "highway" in tags:
        state.highway_words.add(words, name, example_limit)
    return True


def _term_rows(stats: TermStats, top: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for term, occurrences in stats.occurrences.most_common(top):
        object_count = stats.objects[term]
        # Heuristic only: how many characters could theoretically be saved if each
        # word in the term were shortened to roughly three characters.
        words = term.split()
        compact_floor = sum(min(len(word), 3) for word in words) + max(len(words) - 1, 0)
        potential_per_use = max(len(term) - compact_floor, 0)
        rows.append(
            {
                "term": term,
                "objects": object_count,
                "occurrences": occurrences,
                "potential_saving_score": occurrences * potential_per_use,
                "examples": stats.examples.get(term, []),
            }
        )
    return rows


def build_report(state: AuditState, source: Path, limit: int, top: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "input": str(source.resolve()),
        "limit": limit,
        "objects_seen": state.objects_seen,
        "long_names": state.long_names,
        "by_kind": dict(state.by_kind.most_common()),
        "by_geometry": dict(state.by_geometry.most_common()),
        "by_length": dict(state.by_length),
        "by_primary_tag": dict(state.by_primary_tag.most_common()),
        "linear_by_tag": dict(state.linear_by_tag.most_common()),
        "top_words": _term_rows(state.words, top),
        "top_bigrams": _term_rows(state.bigrams, top),
        "top_trigrams": _term_rows(state.trigrams, top),
        "top_highway_words": _term_rows(state.highway_words, top),
        "examples_by_primary_tag": dict(state.examples_by_tag),
    }


def _write_summary_tsv(report: Mapping[str, object], path: Path) -> None:
    lines = ["section\tkey\tcount"]
    sections = ("by_kind", "by_geometry", "by_length", "by_primary_tag", "linear_by_tag")
    for section in sections:
        values = report.get(section, {})
        if isinstance(values, Mapping):
            for key, count in values.items():
                lines.append(f"{section}\t{key}\t{count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clean_tsv(value: object) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _write_terms_tsv(report: Mapping[str, object], path: Path) -> None:
    lines = ["section\tterm\tobjects\toccurrences\tpotential_saving_score\texamples"]
    for section in ("top_words", "top_bigrams", "top_trigrams", "top_highway_words"):
        rows = report.get(section, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            examples = " | ".join(str(item) for item in row.get("examples", []))
            lines.append(
                "\t".join(
                    _clean_tsv(value)
                    for value in (
                        section,
                        row.get("term", ""),
                        row.get("objects", 0),
                        row.get("occurrences", 0),
                        row.get("potential_saving_score", 0),
                        examples,
                    )
                )
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_pbf(
    input_path: str | Path,
    output_prefix: str | Path,
    *,
    limit: int = DEFAULT_LIMIT,
    top: int = DEFAULT_TOP,
    example_limit: int = DEFAULT_EXAMPLES,
) -> dict[str, object]:
    source = Path(input_path)
    if not source.is_file() or source.stat().st_size == 0:
        raise StageError(f"audit input is missing or empty: {source}")
    if limit < 1 or top < 1 or example_limit < 0:
        raise StageError("limit/top must be positive and example_limit must be non-negative")
    try:
        import osmium  # type: ignore[import-not-found]
    except ImportError as exc:
        raise StageError("Python package 'osmium' is required for long-name audit") from exc

    state = AuditState()
    started = time.monotonic()
    _emit_progress(f"[long-names] start: {source.name} ({source.stat().st_size / (1024 ** 3):.2f} GiB)")
    for item in osmium.FileProcessor(str(source)):
        state.objects_seen += 1
        if state.objects_seen % PROGRESS_EVERY_OBJECTS == 0:
            elapsed = max(time.monotonic() - started, 0.001)
            _emit_progress(
                f"[long-names] {state.objects_seen:,} objects; "
                f"{state.objects_seen / elapsed:,.0f} obj/s; {state.long_names:,} long names"
            )
        tags = {str(key): str(value) for key, value in item.tags}
        name = tags.get("name")
        if not name:
            continue
        add_name_to_state(
            state,
            name=name,
            tags=tags,
            kind=_object_kind(item),
            geometry=_way_geometry(item),
            object_id=int(item.id),
            limit=limit,
            example_limit=example_limit,
        )

    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(state, source, limit, top)
    json_path = prefix.with_suffix(".json")
    summary_path = prefix.with_name(prefix.name + "-summary.tsv")
    terms_path = prefix.with_name(prefix.name + "-terms.tsv")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_summary_tsv(report, summary_path)
    _write_terms_tsv(report, terms_path)
    elapsed = max(time.monotonic() - started, 0.001)
    _emit_progress(
        f"[long-names] done: {state.objects_seen:,} objects; {state.long_names:,} names > {limit}; "
        f"{elapsed:.1f}s"
    )
    return report

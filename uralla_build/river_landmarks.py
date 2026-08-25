"""Static river-landmark catalogue support."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Mapping
import unicodedata

from .errors import StageError


RIVER_RANK_TAG = "uralla:river_rank"
DEFAULT_RIVER_CATALOG = Path(__file__).resolve().parents[1] / "catalog/river-landmarks.tsv"
RIVER_NAME_KEYS = ("name", "name:ru", "name:en", "int_name")


def normalize_river_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized, flags=re.IGNORECASE)
    return " ".join(normalized.split())


def load_river_landmarks(path: str | Path = DEFAULT_RIVER_CATALOG) -> dict[str, int]:
    """Load normalized river names/aliases mapped to stable display ranks."""

    catalog_path = Path(path)
    try:
        lines = catalog_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise StageError(f"cannot load river landmark catalogue {catalog_path}: {exc}") from exc

    landmarks: dict[str, int] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        if len(fields) < 5:
            raise StageError(
                f"river landmark catalogue {catalog_path}:{line_number} must have 5 TSV fields"
            )
        rank_text, length_text, name, aliases, _origin = (field.strip() for field in fields[:5])
        if rank_text.casefold() == "rank":
            continue
        try:
            rank = int(rank_text)
            length_km = int(length_text)
        except ValueError as exc:
            raise StageError(
                f"river landmark catalogue {catalog_path}:{line_number} has invalid rank/length"
            ) from exc
        if rank not in {1, 2, 3, 4} or length_km <= 0 or not name:
            raise StageError(
                f"river landmark catalogue {catalog_path}:{line_number} has invalid values"
            )
        values = [name]
        if aliases:
            values.extend(alias.strip() for alias in aliases.split("|") if alias.strip())
        for value in values:
            normalized = normalize_river_name(value)
            if not normalized:
                continue
            existing = landmarks.get(normalized)
            if existing is not None and existing != rank:
                raise StageError(
                    f"river landmark catalogue {catalog_path}:{line_number} gives {value!r} conflicting ranks"
                )
            landmarks[normalized] = rank
    return landmarks


def enrich_river_landmark_tags(
    tags: Mapping[str, str] | object,
    landmarks: Mapping[str, int],
) -> tuple[dict[str, str], bool]:
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if result.get("waterway") != "river":
        return result, False

    rank: int | None = None
    for key in RIVER_NAME_KEYS:
        value = result.get(key)
        if not value:
            continue
        candidate = landmarks.get(normalize_river_name(value))
        if candidate is not None:
            rank = candidate if rank is None else min(rank, candidate)
    if rank is None:
        return result, False

    value = str(rank)
    changed = result.get(RIVER_RANK_TAG) != value
    result[RIVER_RANK_TAG] = value
    return result, changed

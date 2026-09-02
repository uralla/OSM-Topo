"""Semantic detection for kite spots, schools, stations, and related infrastructure."""

from __future__ import annotations

import re
from typing import Mapping


KITE_POI_TAG = "uralla:kite"

# Match the root at the beginning of a word so common forms such as
# "кайт", "кайтстанция", "кайтсерфинг", "kite", "kitesurfing" and
# "kite-school" are accepted without depending on one particular OSM schema.
_KITE_VALUE_RE = re.compile(r"(?<![0-9a-zа-яё])(?:кайт|kite)", re.IGNORECASE)


def is_kite_infrastructure(tags: Mapping[str, str] | object) -> bool:
    """Return True when any tag value identifies kite-related infrastructure."""
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    for _key, raw_value in items:
        value = str(raw_value)
        if value and _KITE_VALUE_RE.search(value):
            return True
    return False


def enrich_kite_tags(tags: Mapping[str, str] | object) -> tuple[dict[str, str], bool]:
    """Add one stable semantic tag consumed by the Garmin style."""
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if not is_kite_infrastructure(result):
        return result, False
    changed = result.get(KITE_POI_TAG) != "yes"
    result[KITE_POI_TAG] = "yes"
    return result, changed

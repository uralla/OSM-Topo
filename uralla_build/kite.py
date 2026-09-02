"""Semantic detection for kite spots, schools, stations, and related infrastructure."""

from __future__ import annotations

import re
from typing import Mapping


KITE_POI_TAG = "uralla:kite"

# Match the distinctive Russian/English root wherever it occurs.  Besides
# suffix forms such as "кайтспот" and "kitesurfing", this deliberately accepts
# prefixed forms such as "snowkite" and "landkite".  OSM tagging is inconsistent,
# so both keys and values are inspected below.
_KITE_TEXT_RE = re.compile(r"(?:кайт|kite)", re.IGNORECASE)


def is_kite_infrastructure(tags: Mapping[str, str] | object) -> bool:
    """Return True when any tag key or value identifies kite infrastructure."""
    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    for raw_key, raw_value in items:
        key = str(raw_key)
        value = str(raw_value)
        # Do not let our own derived tag make this semantic detector self-fulfilling.
        if key != KITE_POI_TAG and _KITE_TEXT_RE.search(key):
            return True
        if value and _KITE_TEXT_RE.search(value):
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

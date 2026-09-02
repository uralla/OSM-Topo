"""Focused Russian sanatorium display-label compaction."""

from __future__ import annotations

from typing import Mapping
import re


DISPLAY_LABEL_TAG = "uralla:label"


def _is_sanatorium_context(tags: Mapping[str, str]) -> bool:
    if tags.get("healthcare") in {"sanatorium", "rehabilitation"}:
        return True
    if tags.get("amenity") in {"clinic", "hospital", "nursing_home"}:
        return True
    if tags.get("tourism") in {"hotel", "resort", "guest_house", "motel", "hostel"}:
        return True
    return tags.get("leisure") == "resort"


def enrich_sanatorium_label_tags(
    tags: Mapping[str, str] | object,
) -> tuple[dict[str, str], bool]:
    """Compact common Russian sanatorium honorific wording without touching name=."""

    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]
    result = {str(key): str(value) for key, value in items}
    if not _is_sanatorium_context(result):
        return result, False

    name = result.get("name")
    if not name:
        return result, False

    match = re.fullmatch(
        r"\s*санаторий\s+имени\s+академика\s+"
        r"(?:(?:[А-ЯЁ]\.)\s*){1,3}(.+?)\s*",
        name,
        re.IGNORECASE,
    )
    if not match:
        return result, False

    surname = match.group(1).strip()
    if not surname:
        return result, False
    label = f"Сан. им. академика {surname}"
    changed = result.get(DISPLAY_LABEL_TAG) != label
    result[DISPLAY_LABEL_TAG] = label
    return result, changed

"""Final adaptive POI LOD classification.

This module deliberately contains only the combination logic. Spatial signals are
computed in poi_context.py; the style will consume the final class only after the
new model has been validated against real Garmin renders.
"""

from __future__ import annotations


POI_LOD_CLASS_TAG = "uralla:poi_lod_class"

_CLASS_SCORE = {"L": 0, "M": 1, "H": 2}


def classify_poi_lod(
    *,
    priority: str,
    activity_context: str,
    screen_pressure: str,
    intrinsic_floor: str = "L",
) -> str:
    """Combine rarity, remoteness, screen pressure, and category importance.

    H -> resolution 22
    M -> resolution 23
    L -> resolution 24

    Rarity supplies the normal floor: isolated POIs are always H and sparse POIs
    are never lower than M. Remote semantic context and low visual pressure can
    promote a POI by one step each. Low pressure is intentionally ignored in
    urban context so a local visual gap inside a city does not promote ordinary
    POIs too far.

    ``intrinsic_floor`` preserves category-level importance independently of
    spatial rarity. For example, supermarkets retain at least M/resolution 23
    even when they are common and urban.
    """

    score = {
        "common": 0,
        "sparse": 1,
        "isolated": 2,
    }.get(priority, 0)

    if activity_context == "remote":
        score += 1
    if screen_pressure == "low" and activity_context != "urban":
        score += 1

    score = max(score, _CLASS_SCORE.get(intrinsic_floor, 0))

    if score >= 2:
        return "H"
    if score == 1:
        return "M"
    return "L"

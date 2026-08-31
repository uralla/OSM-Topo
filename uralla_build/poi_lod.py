"""Final adaptive POI LOD classification.

This module deliberately contains only the combination logic. Spatial signals are
computed in poi_context.py; the style will consume the final class only after the
new model has been validated against real Garmin renders.
"""

from __future__ import annotations


POI_LOD_CLASS_TAG = "uralla:poi_lod_class"


def classify_poi_lod(*, priority: str, activity_context: str, screen_pressure: str) -> str:
    """Combine rarity, semantic remoteness, and visual screen pressure into H/M/L.

    H -> resolution 22
    M -> resolution 23
    L -> resolution 24

    Rarity is the floor: isolated POIs are always H and sparse POIs are never
    lower than M. Remote semantic context and low visual pressure can promote a
    POI by one step each. Low pressure is intentionally ignored in urban context
    so a local visual gap inside a city does not promote ordinary POIs too far.
    """

    base = {
        "common": 0,
        "sparse": 1,
        "isolated": 2,
    }.get(priority, 0)

    score = base
    if activity_context == "remote":
        score += 1
    if screen_pressure == "low" and activity_context != "urban":
        score += 1

    if score >= 2:
        return "H"
    if score == 1:
        return "M"
    return "L"

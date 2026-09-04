from pathlib import Path

from uralla_build.peak_landmark_ids import (
    enrich_peak_landmark_item,
    load_peak_landmark_node_ids,
)
from uralla_build.preprocessor import PEAK_LANDMARK_TAG, load_peak_landmarks


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "peak-landmarks.tsv"
LANDUSE_POINTS = ROOT / "styles" / "uralla" / "inc" / "landuse_points"


class Node:
    def __init__(self, node_id: int) -> None:
        self.id = node_id

    def type_str(self) -> str:
        return "node"


def test_big_iremel_exact_osm_node_is_a_landmark_without_wikidata() -> None:
    qids = load_peak_landmarks(CATALOG)
    node_ids = load_peak_landmark_node_ids(CATALOG)

    tags, changed = enrich_peak_landmark_item(
        Node(365668953),
        {"natural": "peak", "name": "Большой Иремель", "ele": "1582"},
        qids,
        node_ids,
    )

    assert changed is True
    assert tags[PEAK_LANDMARK_TAG] == "yes"
    assert 365668953 in node_ids


def test_small_iremel_is_not_promoted_by_nearby_name() -> None:
    qids = load_peak_landmarks(CATALOG)
    node_ids = load_peak_landmark_node_ids(CATALOG)

    tags, changed = enrich_peak_landmark_item(
        Node(999999999),
        {"natural": "peak", "name": "Малый Иремель", "ele": "1449"},
        qids,
        node_ids,
    )

    assert changed is False
    assert PEAK_LANDMARK_TAG not in tags


def test_generic_named_peaks_do_not_enter_resolution_21_22() -> None:
    text = LANDUSE_POINTS.read_text(encoding="utf-8")

    assert "natural=peak & ele=* & name=* & note!=great-peak | natural=hill & ele=* & name=* {name \"${name}\"} [0x6619 resolution 21-22 continue]" not in text
    assert "[0x6614 resolution 23-24 continue]" in text
    assert "natural=peak & name='Большой Иремель'" not in text
    assert "note=great-peak {name" not in text

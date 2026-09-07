from pathlib import Path

from uralla_build.peak_landmark_ids import (
    enrich_peak_landmark_item,
    load_peak_landmark_node_ids,
)
from uralla_build.preprocessor import PEAK_LANDMARK_TAG, load_peak_landmarks


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "peak-landmarks.tsv"
LANDUSE_POINTS = ROOT / "styles" / "uralla" / "inc" / "landuse_points"
PEAK_PRIORITY = ROOT / "styles" / "uralla" / "inc" / "peak_priority"


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


def test_small_iremel_is_explicitly_blocked_from_landmark_style() -> None:
    text = PEAK_PRIORITY.read_text(encoding="utf-8")

    raw = "natural=peak & name='Малый Иремель'"
    normalized = "natural=peak & uralla:label='Малый Иремель'"
    landmark = "uralla:peak_landmark=yes {add note=great-peak}"
    assert raw in text
    assert normalized in text
    assert "{delete uralla:peak_landmark; delete note}" in text
    assert text.index(raw) < text.index(landmark)
    assert text.index(normalized) < text.index(landmark)


def test_generic_peaks_and_hills_are_resolution_24_only() -> None:
    text = LANDUSE_POINTS.read_text(encoding="utf-8")

    assert "[0x6614 resolution 23-24 continue]" not in text
    assert "[0x6619 resolution 23-24 continue]" not in text
    assert '[0x6614 resolution 24 continue]' in text
    assert '[0x6619 resolution 24 continue]' in text
    assert "natural=peak & name='Большой Иремель'" not in text
    assert "note=great-peak {name" not in text


def test_big_iremel_landmark_still_owns_overview_levels() -> None:
    text = PEAK_PRIORITY.read_text(encoding="utf-8")

    assert "uralla:peak_landmark=yes {add note=great-peak}" in text
    assert 'note=great-peak {name "${name}"} [0x6616 resolution 16-22 continue]' in text
    assert 'note=great-peak & ele=* {name "${name} (${ele} м)"} [0x6616 resolution 23-24]' in text

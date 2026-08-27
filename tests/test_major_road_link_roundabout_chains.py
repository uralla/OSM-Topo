from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINES = (ROOT / "styles/uralla/lines").read_text(encoding="utf-8")


def test_primary_secondary_tertiary_link_roundabout_chains_stop_after_close_lod():
    expected_far = (
        "highway=primary_link & length()>500 | highway=primary & junction=roundabout & length()>500 [0x03 resolution 20-21 continue]",
        "highway=secondary_link & length()>500 | highway=secondary & junction=roundabout & length()>500 [0x07 resolution 20-21 continue]",
        "highway=tertiary_link & length()>500 | highway=tertiary & junction=roundabout & length()>500 [0x07 resolution 21-22 continue]",
    )
    expected_close = (
        "highway=primary_link | highway=primary & junction=roundabout [0x03 road_class=3 road_speed=5 resolution 22]",
        "highway=secondary_link | highway=secondary & junction=roundabout [0x04 road_class=2 road_speed=5 resolution 22]",
        "highway=tertiary_link | highway=tertiary & junction=roundabout [0x11 road_class=2 road_speed=5 resolution 23]",
    )

    for rule in expected_far:
        assert rule in LINES

    for rule in expected_close:
        assert rule in LINES
        assert rule + " continue" not in LINES

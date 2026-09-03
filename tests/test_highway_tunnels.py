from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TUNNELS = ROOT / "styles" / "uralla" / "inc" / "tunnels"
TYP = ROOT / "styles" / "uralla.txt"


def _text() -> str:
    return TUNNELS.read_text(encoding="utf-8")


def test_highway_tunnels_use_only_tunnel_visual_and_invisible_carrier() -> None:
    text = _text()
    assert "0x10e04" in text
    assert "0x1b road_class=" in text
    for road_type in ("0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07", "0x0a", "0x13"):
        assert f"[{road_type} " not in text


def test_major_tunnel_routing_classes_match_ordinary_roads() -> None:
    text = _text()
    expected = (
        "highway=motorway & tunnel=yes [0x1b road_class=4 road_speed=6 resolution 16]",
        "highway=motorway_link & tunnel=yes [0x1b road_class=4 road_speed=4 resolution 19]",
        "highway=trunk & tunnel=yes [0x1b road_class=4 road_speed=6 resolution 14]",
        "highway=trunk_link & tunnel=yes [0x1b road_class=4 road_speed=6 resolution 18]",
        "highway=primary & tunnel=yes [0x1b road_class=3 road_speed=5 resolution 17]",
        "highway=secondary & tunnel=yes [0x1b road_class=2 road_speed=5 resolution 20]",
        "highway=tertiary & tunnel=yes [0x1b road_class=1 road_speed=4 resolution 23]",
    )
    for rule in expected:
        assert rule in text


def test_tunnel_overview_thresholds_are_softer_than_ordinary_roads() -> None:
    text = _text()
    assert "highway=secondary & tunnel=yes & length()>250 [0x10e04 resolution 18-19 continue]" in text
    assert "highway=tertiary & tunnel=yes & length()>250 [0x10e04 resolution 19-22 continue]" in text
    assert "highway=track & tracktype=grade1 & tunnel=yes & length()>50 [0x10e04 resolution 21-23 continue]" in text
    assert "highway=track & tracktype!=grade1 & tunnel=yes & length()>50 [0x10e04 resolution 22-23 continue]" in text
    assert "highway=cycleway & tunnel=yes & length()>100 [0x10e04 resolution 22-23 continue]" in text


def test_local_tunnel_hierarchy_matches_ordinary_roads() -> None:
    text = _text()
    expected = (
        "highway=minor & tunnel=yes [0x1b road_class=1 road_speed=4 resolution 22]",
        "highway=unclassified & ref=* & tunnel=yes [0x1b road_class=1 road_speed=4 resolution 22]",
        "highway=unclassified & ref!=* & tunnel=yes [0x1b road_class=0 road_speed=3 resolution 23]",
        "highway=living_street & tunnel=yes [0x1b road_class=0 road_speed=2 resolution 24]",
        "highway=residential & tunnel=yes [0x1b road_class=0 road_speed=3 resolution 24]",
        "highway=service & tunnel=yes [0x1b road_class=0 road_speed=2 resolution 24]",
    )
    for rule in expected:
        assert rule in text


def test_routing_carrier_type_0x1b_remains_explicitly_invisible() -> None:
    typ = TYP.read_text(encoding="utf-8")
    match = re.search(r"\[_line\]\nType=0x1b\n.*?\n\[end\]", typ, re.S)
    assert match
    block = match.group(0)
    assert '"1 c none"' in block
    assert "LineWidth=" not in block
    assert "BorderWidth=" not in block

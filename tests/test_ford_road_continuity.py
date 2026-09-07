from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / "styles" / "uralla" / "lines"


def test_classified_ford_is_overlay_and_keeps_base_highway_processing() -> None:
    text = LINES.read_text(encoding="utf-8")

    overlay = "ford=yes & highway=* & area!=yes [0x11002 resolution 24 continue]"
    standalone = "highway=ford & area!=yes [0x11002 resolution 24]"

    assert overlay in text
    assert standalone in text
    assert "highway=* & highway!=ford & ford=yes [0x12" not in text
    assert "highway=ford [0x12" not in text


def test_ford_overlay_runs_before_normal_road_ownership() -> None:
    text = LINES.read_text(encoding="utf-8")

    ford = text.index("ford=yes & highway=* & area!=yes")
    tunnel_include = text.index("include 'inc/tunnels';")
    primary = text.index("highway=primary [0x03 road_class=3 road_speed=5 resolution 17]")

    assert ford < tunnel_include < primary

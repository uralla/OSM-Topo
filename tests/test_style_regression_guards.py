from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / "styles" / "uralla" / "lines"
TUNNELS = ROOT / "styles" / "uralla" / "inc" / "tunnels"
PLACE_POINTS = ROOT / "styles" / "uralla" / "inc" / "place_points"
PEAK_PRIORITY = ROOT / "styles" / "uralla" / "inc" / "peak_priority"


def test_restored_tertiary_identity_and_lod():
    text = LINES.read_text(encoding="utf-8")
    assert "highway=tertiary_link | highway=tertiary & junction=roundabout [0x11 road_class=2 road_speed=5 resolution 23]" in text
    assert "highway=tertiary & length()>500 [0x07 resolution 18-19 continue]" in text
    assert "highway=tertiary [0x11 road_class=2 road_speed=5 resolution 20]" in text
    assert "highway=tertiary [0x05 road_class=1 road_speed=4 resolution 23]" not in text


def test_unclassified_precedes_forest_track_on_overview():
    text = LINES.read_text(encoding="utf-8")
    assert "highway=unclassified & length()>500 [0x07 resolution 19-21 continue]" in text
    assert "highway=unclassified & junction!=roundabout [0x06 road_class=1 road_speed=4 resolution 22 continue]" in text
    assert "highway=track & tracktype!=grade1 & length()>100 {add mkgmap:display_name = '${name}'} [0x12 resolution 22-23 continue]" in text


def test_marked_routes_keep_far_zoom_and_routing_preference():
    text = LINES.read_text(encoding="utf-8")
    expected = (
        "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x07 resolution 21-22 continue]",
        "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x0e road_class=0 road_speed=2 resolution 23-24]",
        "mkgmap:trail_name=* & bicycle=yes & highway=path & length()>100 [0x16 road_class=0 road_speed=2 resolution 23-24]",
        "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x12 resolution 21-22 continue]",
        "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x13 road_class=0 road_speed=2 resolution 23-24]",
        "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x07 resolution 20-22 continue]",
        "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x0a road_class=0 road_speed=2 resolution 23-24]",
    )
    for rule in expected:
        assert rule in text


def test_service_and_special_purpose_road_rules_are_not_collapsed():
    text = LINES.read_text(encoding="utf-8")
    for rule in (
        "highway=service & (service=alley|service=driveway) [0x07 resolution 23-23 continue]",
        "highway=service & (service=alley|service=driveway) [0x0d road_class=0 road_speed=0 resolution 24]",
        "highway=service & oneway=yes [0x0d road_class=0 road_speed=1 resolution 24]",
        "highway=service & length()>200 [0x07 resolution 23-23 continue]",
        "highway=service [0x0d road_class=0 road_speed=2 resolution 24]",
        "highway=via_ferrata [0x2e resolution 24]",
        "highway=raceway [0x07 resolution 24]",
        "highway=busway | highway=bus_guideway [0x07 resolution 24]",
        "highway=corridor [0x16 road_class=0 road_speed=0 resolution 24]",
        "highway=platform [0x16 resolution 24]",
    ):
        assert rule in text


def test_density_stays_below_tertiary():
    text = LINES.read_text(encoding="utf-8")
    assert text.index("highway=tertiary [0x11 road_class=2 road_speed=5 resolution 20]") < text.index("include 'inc/road_density';")
    assert text.index("include 'inc/road_density';") < text.index("highway=minor & length()>400")


def test_tertiary_tunnel_keeps_single_0x08_but_restored_routing_class():
    text = TUNNELS.read_text(encoding="utf-8")
    assert "highway=tertiary & tunnel=yes & length()>250 [0x08 road_class=2 road_speed=5 resolution 18]" in text
    assert "highway=tertiary & tunnel=yes [0x08 road_class=2 road_speed=5 resolution 20]" in text
    assert "(highway=tertiary_link | highway=tertiary & junction=roundabout) & tunnel=yes [0x08 road_class=2 road_speed=5 resolution 23]" in text
    assert "0x10e04" not in text


def test_big_iremel_is_an_early_far_zoom_peak_anchor():
    place = PLACE_POINTS.read_text(encoding="utf-8")
    peaks = PEAK_PRIORITY.read_text(encoding="utf-8")
    assert "include 'peak_priority';" in place
    assert "natural=peak & name='Большой Иремель'" in peaks
    assert "note=great-peak {name \"${name}\"} [0x6616 resolution 16-22 continue]" in peaks
    assert place.index("include 'peak_priority';") < place.index("place=city")

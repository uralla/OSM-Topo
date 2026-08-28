from pathlib import Path
import re


LINES = Path("styles/uralla/lines")
TYP = Path("styles/uralla.txt")


def _active_airfield_rules():
    text = LINES.read_text()
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("aeroway=runway & highway!=*")
        or line.strip().startswith("(aeroway=taxiway | aeroway=taxilane) & highway!=*")
    ]


def _routing_airfield_rules():
    text = LINES.read_text()
    return [
        line.strip()
        for line in text.splitlines()
        if ("abandoned:aeroway=" in line or "abandoned=yes" in line)
        and "road_class=1" in line
        and "road_speed=4" in line
    ]


def test_active_airfield_line_types_match_original_nonrouting_scheme():
    rules = _active_airfield_rules()
    assert "aeroway=runway & highway!=* & is_closed()=false {name '${ref}'} [0x27 resolution 20]" in rules
    assert "(aeroway=taxiway | aeroway=taxilane) & highway!=* & is_closed()=false {name '${ref}'} [0x1a resolution 23]" in rules


def test_active_airfield_lines_do_not_define_routing_attributes():
    for rule in _active_airfield_rules():
        assert not re.search(r"\broad[_-](?:class|speed)\b", rule, re.I), rule
        assert "mkgmap:road-class" not in rule
        assert "mkgmap:road-speed" not in rule


def test_abandoned_runways_keep_runway_visual_and_use_invisible_routing_carrier():
    text = LINES.read_text()
    lifecycle_visual = "((abandoned:aeroway=runway | disused:aeroway=runway) & (surface=asphalt | surface=concrete | surface=concrete:lanes | surface=concrete:plates | surface=paved)) [0x27 resolution 20 continue]"
    lifecycle_carrier = "((abandoned:aeroway=runway | disused:aeroway=runway) & (surface=asphalt | surface=concrete | surface=concrete:lanes | surface=concrete:plates | surface=paved)) [0x1b road_class=1 road_speed=4 resolution 22]"
    legacy_visual = "(aeroway=runway & (abandoned=yes | disused=yes) & (surface=asphalt | surface=concrete | surface=concrete:lanes | surface=concrete:plates | surface=paved)) [0x27 resolution 20 continue]"
    legacy_carrier = "(aeroway=runway & (abandoned=yes | disused=yes) & (surface=asphalt | surface=concrete | surface=concrete:lanes | surface=concrete:plates | surface=paved)) [0x1b road_class=1 road_speed=4 resolution 22]"
    for rule in (lifecycle_visual, lifecycle_carrier, legacy_visual, legacy_carrier):
        assert rule in text


def test_abandoned_taxiways_keep_taxiway_visual_and_are_routable():
    rules = _routing_airfield_rules()
    taxi_rules = [rule for rule in rules if "taxiway" in rule or "taxilane" in rule]
    assert len(taxi_rules) == 2
    for rule in taxi_rules:
        assert "[0x1a road_class=1 road_speed=4 resolution 23]" in rule
        assert "surface=asphalt" in rule
        assert "surface=concrete" in rule
        assert "surface=paved" in rule


def test_taxiway_type_0x1a_has_explicit_typ_definition():
    typ = TYP.read_text()
    match = re.search(r"\[_line\]\nType=0x1a\n.*?\n\[end\]", typ, re.S)
    assert match
    block = match.group(0)
    assert "LineWidth=6" in block
    assert "BorderWidth=1" in block
    assert "String1=0x19,рулёжная дорожка" in block
    assert "String2=0x04,taxiway" in block


def test_runway_routing_carrier_0x1b_is_explicit_and_invisible():
    typ = TYP.read_text()
    match = re.search(r"\[_line\]\nType=0x1b\n.*?\n\[end\]", typ, re.S)
    assert match
    block = match.group(0)
    assert '"1 c none"' in block
    assert "LineWidth=" not in block
    assert "BorderWidth=" not in block

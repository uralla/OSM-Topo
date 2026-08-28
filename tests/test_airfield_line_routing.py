from pathlib import Path
import re


LINES = Path("styles/uralla/lines")
TYP = Path("styles/uralla.txt")


def _active_airfield_rules():
    text = LINES.read_text()
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("aeroway=runway")
        or line.strip().startswith("(aeroway=taxiway | aeroway=taxilane)")
    ]


def _routing_airfield_rules():
    text = LINES.read_text()
    return [
        line.strip()
        for line in text.splitlines()
        if "abandoned:aeroway=" in line
        or (
            line.strip().startswith("((aeroway=runway | aeroway=taxiway | aeroway=taxilane)")
            and "abandoned=yes" in line
        )
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


def test_abandoned_and_disused_paved_airfield_ways_are_routable():
    rules = _routing_airfield_rules()
    assert len(rules) == 2
    for rule in rules:
        assert "road_class=1" in rule
        assert "road_speed=4" in rule
        assert "surface=asphalt" in rule
        assert "surface=concrete" in rule
        assert "surface=paved" in rule
    lifecycle_rule = next(rule for rule in rules if "abandoned:aeroway=" in rule)
    for aeroway in ("runway", "taxiway", "taxilane"):
        assert f"abandoned:aeroway={aeroway}" in lifecycle_rule
        assert f"disused:aeroway={aeroway}" in lifecycle_rule


def test_taxiway_type_0x1a_has_explicit_typ_definition():
    typ = TYP.read_text()
    match = re.search(r"\[_line\]\nType=0x1a\n.*?\n\[end\]", typ, re.S)
    assert match
    block = match.group(0)
    assert "LineWidth=6" in block
    assert "BorderWidth=1" in block
    assert "String1=0x19,рулёжная дорожка" in block
    assert "String2=0x04,taxiway" in block

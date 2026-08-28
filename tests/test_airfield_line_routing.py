from pathlib import Path
import re


LINES = Path("styles/uralla/lines")


def _airfield_rules():
    text = LINES.read_text()
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("aeroway=runway")
        or line.strip().startswith("(aeroway=taxiway | aeroway=taxilane)")
    ]


def test_airfield_line_types_match_original_nonrouting_scheme():
    rules = _airfield_rules()
    assert "aeroway=runway & highway!=* & is_closed()=false {name '${ref}'} [0x27 resolution 20]" in rules
    assert "(aeroway=taxiway | aeroway=taxilane) & highway!=* & is_closed()=false {name '${ref}'} [0x1a resolution 23]" in rules


def test_airfield_lines_do_not_define_routing_attributes():
    for rule in _airfield_rules():
        assert not re.search(r"\broad[_-](?:class|speed)\b", rule, re.I), rule
        assert "mkgmap:road-class" not in rule
        assert "mkgmap:road-speed" not in rule

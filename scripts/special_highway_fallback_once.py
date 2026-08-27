from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
anchor = "# Mop up any unrecognised highway types\nhighway=* & area!=yes & highway!=path & highway!=steps & highway!=footway & highway!=track & highway!=cycleway & highway!=service [0x07 road_class=0 road_speed=0 resolution 24]"
replacement = """# Special-purpose highways must not become generic motor-routing roads when access tags are incomplete.
highway=raceway [0x07 resolution 24]
highway=escape [0x07 resolution 24]
highway=busway | highway=bus_guideway [0x07 resolution 24]

# Mop up any unrecognised highway types
highway=* & area!=yes & highway!=path & highway!=steps & highway!=footway & highway!=track & highway!=cycleway & highway!=service [0x07 road_class=0 road_speed=0 resolution 24]"""
if anchor not in lines:
    raise SystemExit('generic highway fallback not found')
LINES.write_text(lines.replace(anchor, replacement, 1), encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor_test = "    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:\n"
if anchor_test not in test:
    raise SystemExit('test anchor not found')
block = '''    def test_special_purpose_highways_do_not_enter_generic_motor_routing(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        fallback = "highway=* & area!=yes & highway!=path & highway!=steps & highway!=footway & highway!=track & highway!=cycleway & highway!=service [0x07 road_class=0 road_speed=0 resolution 24]"\n        for rule in (\n            "highway=raceway [0x07 resolution 24]",\n            "highway=escape [0x07 resolution 24]",\n            "highway=busway | highway=bus_guideway [0x07 resolution 24]",\n        ):\n            self.assertIn(rule, lines)\n            self.assertLess(lines.index(rule), lines.index(fallback))\n            self.assertNotIn(rule.replace("resolution 24", "road_class=0 road_speed=0 resolution 24"), lines)\n\n'''
TEST.write_text(test.replace(anchor_test, block + anchor_test, 1), encoding='utf-8', newline='\n')

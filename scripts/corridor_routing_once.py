from pathlib import Path

LINES = Path('styles/uralla/lines')
ACCESS = Path('styles/uralla/inc/access')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
anchor = "highway=busway | highway=bus_guideway [0x07 resolution 24]\n\n# Mop up any unrecognised highway types"
replacement = "highway=busway | highway=bus_guideway [0x07 resolution 24]\n# Indoor corridors are pedestrian ways, not generic motor roads.\nhighway=corridor [0x16 road_class=0 road_speed=0 resolution 24]\n\n# Mop up any unrecognised highway types"
if anchor not in lines:
    raise SystemExit('special highway block not found')
LINES.write_text(lines.replace(anchor, replacement, 1), encoding='utf-8', newline='\n')

access = ACCESS.read_text(encoding='utf-8')
anchor = "highway=footway                            { add bicycle=yes; add foot=yes; add access=no }\n"
replacement = anchor + "highway=corridor                           { add foot=yes; add access=no }\n"
if anchor not in access:
    raise SystemExit('footway access rule not found')
ACCESS.write_text(access.replace(anchor, replacement, 1), encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor_test = "    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:\n"
if anchor_test not in test:
    raise SystemExit('test anchor not found')
block = '''    def test_indoor_corridor_is_foot_routable_not_generic_motor_road(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        access = (STYLE / 'inc' / 'access').read_text(encoding='utf-8')\n        corridor = "highway=corridor [0x16 road_class=0 road_speed=0 resolution 24]"\n        fallback = "highway=* & area!=yes & highway!=path & highway!=steps & highway!=footway & highway!=track & highway!=cycleway & highway!=service [0x07 road_class=0 road_speed=0 resolution 24]"\n        self.assertIn(corridor, lines)\n        self.assertLess(lines.index(corridor), lines.index(fallback))\n        self.assertIn("highway=corridor                           { add foot=yes; add access=no }", access)\n\n'''
TEST.write_text(test.replace(anchor_test, block + anchor_test, 1), encoding='utf-8', newline='\n')

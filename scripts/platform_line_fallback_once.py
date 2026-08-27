from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
anchor = "# Indoor corridors are pedestrian ways, not generic motor roads.\nhighway=corridor [0x16 road_class=0 road_speed=0 resolution 24]\n\n# Mop up any unrecognised highway types"
replacement = "# Indoor corridors are pedestrian ways, not generic motor roads.\nhighway=corridor [0x16 road_class=0 road_speed=0 resolution 24]\n# Bus/tram platforms may be linear, but they are not motor-routing roads.\nhighway=platform [0x16 resolution 24]\n\n# Mop up any unrecognised highway types"
if anchor not in lines:
    raise SystemExit('special highway anchor not found')
LINES.write_text(lines.replace(anchor, replacement, 1), encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor_test = "    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:\n"
block = '''    def test_linear_highway_platform_is_visible_but_not_motor_routable(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        platform = "highway=platform [0x16 resolution 24]"\n        fallback = "highway=* & area!=yes & highway!=path & highway!=steps & highway!=footway & highway!=track & highway!=cycleway & highway!=service [0x07 road_class=0 road_speed=0 resolution 24]"\n        self.assertIn(platform, lines)\n        self.assertLess(lines.index(platform), lines.index(fallback))\n        self.assertNotIn("highway=platform [0x16 road_class=0", lines)\n\n'''
if anchor_test not in test:
    raise SystemExit('test anchor not found')
TEST.write_text(test.replace(anchor_test, block + anchor_test, 1), encoding='utf-8', newline='\n')

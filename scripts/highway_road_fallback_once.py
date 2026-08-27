from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
old = "highway=road { add mkgmap:dead-end-check = false} [0x05 road_class=0 road_speed=1 resolution 21]"
new = "# highway=road has unknown physical/classification semantics; keep only the routing helper\n# and let the conservative generic highway fallback render it at resolution 24.\nhighway=road { add mkgmap:dead-end-check = false }"
if old not in lines:
    raise SystemExit('highway=road rule not found')
LINES.write_text(lines.replace(old, new, 1), encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor = "    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:\n"
if anchor not in test:
    raise SystemExit('test anchor not found')
block = '''    def test_unknown_highway_road_uses_conservative_generic_fallback(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        helper = "highway=road { add mkgmap:dead-end-check = false }"\n        fallback = "highway=* & area!=yes & highway!=path & highway!=steps & highway!=footway & highway!=track & highway!=cycleway & highway!=service [0x07 road_class=0 road_speed=0 resolution 24]"\n        self.assertIn(helper, lines)\n        self.assertIn(fallback, lines)\n        self.assertLess(lines.index(helper), lines.index(fallback))\n        self.assertNotIn("highway=road { add mkgmap:dead-end-check = false} [0x05 road_class=0 road_speed=1 resolution 21]", lines)\n        self.assertNotRegex(lines, r"highway=road .*\\[0x[0-9a-fA-F]+ .*resolution")\n\n'''
TEST.write_text(test.replace(anchor, block + anchor, 1), encoding='utf-8', newline='\n')

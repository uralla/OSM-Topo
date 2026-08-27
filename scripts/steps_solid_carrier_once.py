from pathlib import Path

lines_path = Path('styles/uralla/lines')
test_path = Path('tests/test_line_fallback_cleanup.py')

lines = lines_path.read_text(encoding='utf-8')
old = "# пешеходные лестницы: stair graphic is an overlay; 0x16 below keeps the way routable.\nhighway=steps [0x12d1f resolution 24 continue]\nhighway=steps [0x16 road_class=0 road_speed=0 resolution 24]"
new = "# пешеходные лестницы: stair graphic overlays a solid routable 0x07 carrier.\nhighway=steps [0x12d1f resolution 24 continue]\nhighway=steps [0x07 road_class=0 road_speed=0 resolution 24]"
if old not in lines:
    raise SystemExit('steps style block not found')
lines_path.write_text(lines.replace(old, new, 1), encoding='utf-8', newline='\n')

test = test_path.read_text(encoding='utf-8')
old = '''    def test_steps_keep_stair_overlay_and_routable_trail_carrier(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        overlay = "highway=steps [0x12d1f resolution 24 continue]"\n        carrier = "highway=steps [0x16 road_class=0 road_speed=0 resolution 24]"\n        self.assertIn(overlay, lines)\n        self.assertIn(carrier, lines)\n        self.assertLess(lines.index(overlay), lines.index(carrier))\n'''
new = '''    def test_steps_keep_stair_overlay_on_solid_routable_carrier(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        overlay = "highway=steps [0x12d1f resolution 24 continue]"\n        carrier = "highway=steps [0x07 road_class=0 road_speed=0 resolution 24]"\n        self.assertIn(overlay, lines)\n        self.assertIn(carrier, lines)\n        self.assertNotIn("highway=steps [0x16 road_class=0 road_speed=0 resolution 24]", lines)\n        self.assertLess(lines.index(overlay), lines.index(carrier))\n'''
if old not in test:
    raise SystemExit('steps regression block not found')
test_path.write_text(test.replace(old, new, 1), encoding='utf-8', newline='\n')

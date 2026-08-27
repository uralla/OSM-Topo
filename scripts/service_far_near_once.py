from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
old = """# parking_aisle is intentionally removed in inc/water_lines.
highway=service & (service=alley|service=driveway) [0x07 road_class=0 road_speed=0 resolution 23]
highway=service & oneway=yes [0x07 road_class=0 road_speed=1 resolution 23]
highway=service & length()>200 [0x07 resolution 23-23 continue]
highway=service [0x0d road_class=0 road_speed=2 resolution 24]
"""
new = """# parking_aisle is intentionally removed in inc/water_lines.
# Service roads use one far/near visual hierarchy; routing speed preserves subtype semantics.
highway=service & (service=alley|service=driveway) [0x07 resolution 23-23 continue]
highway=service & (service=alley|service=driveway) [0x0d road_class=0 road_speed=0 resolution 24]
highway=service & oneway=yes [0x07 resolution 23-23 continue]
highway=service & oneway=yes [0x0d road_class=0 road_speed=1 resolution 24]
highway=service & length()>200 [0x07 resolution 23-23 continue]
highway=service [0x0d road_class=0 road_speed=2 resolution 24]
"""
if old not in lines:
    raise SystemExit('service block not found')
LINES.write_text(lines.replace(old, new, 1), encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor = "    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:\n"
if anchor not in test:
    raise SystemExit('test anchor not found')
block = '''    def test_service_specializations_keep_far_near_hierarchy(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        for rule in (\n            "highway=service & (service=alley|service=driveway) [0x07 resolution 23-23 continue]",\n            "highway=service & (service=alley|service=driveway) [0x0d road_class=0 road_speed=0 resolution 24]",\n            "highway=service & oneway=yes [0x07 resolution 23-23 continue]",\n            "highway=service & oneway=yes [0x0d road_class=0 road_speed=1 resolution 24]",\n            "highway=service & length()>200 [0x07 resolution 23-23 continue]",\n            "highway=service [0x0d road_class=0 road_speed=2 resolution 24]",\n        ):\n            self.assertIn(rule, lines)\n        self.assertNotIn(\n            "highway=service & (service=alley|service=driveway) [0x07 road_class=0 road_speed=0 resolution 23]",\n            lines,\n        )\n        self.assertNotIn(\n            "highway=service & oneway=yes [0x07 road_class=0 road_speed=1 resolution 23]",\n            lines,\n        )\n\n'''
TEST.write_text(test.replace(anchor, block + anchor, 1), encoding='utf-8', newline='\n')

from pathlib import Path
import re

LINES = Path('styles/uralla/lines')
TYP = Path('styles/uralla.txt')
LINE_TEST = Path('tests/test_line_fallback_cleanup.py')
WATER_TEST = Path('tests/test_water_source_typ.py')

# 1) Move lifecycle ownership before all active highway overlays.
lines = LINES.read_text(encoding='utf-8')
lifecycle = '''# Disused/abandoned roads are useful topo landmarks but must never enter active routing.\n(disused:highway=* | abandoned:highway=* | highway=disused | highway=abandoned)\n{ name '${name} (плохая грунтовка/неисп)' | 'плохая грунтовка/неисп' }\n[0x1001a resolution 24]\n# Legacy tagging: keep the object visible in the same language, but stop before normal highway rules.\nhighway=* & (disused=yes | abandoned=yes)\n{ name '${name} (плохая грунтовка/неисп)' | 'плохая грунтовка/неисп'; set mkgmap:numbers=false }\n[0x1001a resolution 24]\n\n'''
if lines.count(lifecycle) != 1:
    raise SystemExit('lifecycle block not found exactly once')
lines = lines.replace(lifecycle, '', 1)
anchor = "# [CUSTOM/АВТОРСКОЕ] Smoothness overlay is only for machine-drivable roads.\n"
if anchor not in lines:
    raise SystemExit('smoothness anchor not found')
lines = lines.replace(anchor, lifecycle + anchor, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

# 2) Remove now-unused 0x2e line graphic and normalize NoLabel syntax.
typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(r"\n\[_line\]\nType=0x2e\n.*?\n\[end\]\n", re.S | re.I)
typ, count = pattern.subn('\n', typ, count=1)
if count != 1:
    raise SystemExit(f'expected one 0x2e line section, removed {count}')
typ = typ.replace('FontStyle=NoLabel (invisible)', 'FontStyle=NoLabel')
TYP.write_text(typ, encoding='utf-8', newline='\n')

# 3) Replace stale marked-route regression with current far/near shift checks and add lifecycle order check.
test = LINE_TEST.read_text(encoding='utf-8')
start = test.index('    def test_marked_trails_use_close_zoom_type_one_level_farther')
end = test.index('    def test_canonical_road_and_trail_near_types_are_routable', start)
replacement = '''    def test_marked_trails_shift_far_and_near_one_level(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        for rule in (\n            "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x07 resolution 21-22 continue]",\n            "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x0e road_class=0 road_speed=1 resolution 23-24]",\n            "mkgmap:trail_name=* & bicycle=yes & highway=path & length()>100 [0x0b resolution 21-22 continue]",\n            "mkgmap:trail_name=* & bicycle=yes & highway=path & length()>100 [0x16 road_class=0 road_speed=1 resolution 23-24]",\n            "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x0b resolution 22-22 continue]",\n            "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x16 road_class=0 road_speed=0 resolution 23-24]",\n            "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x12 resolution 21-22 continue]",\n            "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x13 road_class=0 road_speed=1 resolution 23-24]",\n            "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x07 resolution 20-22 continue]",\n            "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x0a road_class=0 road_speed=1 resolution 23-24]",\n        ):\n            self.assertIn(rule, lines)\n        self.assertNotRegex(lines, r"mkgmap:trail_name=.*resolution 1[0-9]")\n\n    def test_disused_lifecycle_precedes_active_highway_overlays(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        lifecycle = lines.index("(disused:highway=* | abandoned:highway=* | highway=disused | highway=abandoned)")\n        for active in (\n            "Smoothness overlay is only for machine-drivable roads",\n            "highway=* & oneway=yes & highway!=construction",\n            "# зимники и ледовые переправы",\n            "# линии мостов дополнительно к дорогам",\n        ):\n            self.assertLess(lifecycle, lines.index(active))\n\n'''
test = test[:start] + replacement + test[end:]
LINE_TEST.write_text(test, encoding='utf-8', newline='\n')

# 4) TYP source is UTF-8 now; keep the regression aligned with reality.
water = WATER_TEST.read_text(encoding='utf-8')
water = water.replace('TYP.read_text(encoding="cp1251")', 'TYP.read_text(encoding="utf-8")')
WATER_TEST.write_text(water, encoding='utf-8', newline='\n')

print('cleaned lifecycle ordering, stale TYP 0x2e, NoLabel syntax, and regressions')

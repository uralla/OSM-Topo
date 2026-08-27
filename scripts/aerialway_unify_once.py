from pathlib import Path
import re

LINES = Path('styles/uralla/lines')
WATER = Path('styles/uralla/inc/water_lines')
TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
old_block = """## Канатная дорога
# cable_car is consumed in inc/water_lines and uses the non-routable aerialway type 0x10f15.
aerialway=gondola    {name '${name} (${ref})' | '${name}' | '${ref}' } [0x10f01 resolution 22]
aerialway=mixed_lift {name '${name} (${ref})' | '${name}' | '${ref}' } [0x10f02 resolution 22]
aerialway=chair_lift {name '${name} (${ref})' | '${name}' | '${ref}' } [0x10f03 resolution 22]
aerialway=drag_lift  {name '${name} (${ref})' | '${name}' | '${ref}' } [0x10f04 resolution 22]
aerialway=* [0x10f15 resolution 22]
"""
new_block = """## Канатная дорога
# All aerialways share one non-routable visual type; subtype detail stays in OSM tags, not TYP.
aerialway=* {name '${name} (${ref})' | '${name}' | '${ref}' } [0x10f15 resolution 22]
"""
if lines.count(old_block) != 1:
    raise SystemExit(f'expected one aerialway block, got {lines.count(old_block)}')
LINES.write_text(lines.replace(old_block, new_block, 1), encoding='utf-8', newline='\n')

water = WATER.read_text(encoding='utf-8')
old_cable = "aerialway=cable_car { name '${name} (${ref})' | '${name}' | '${ref}' } [0x10f15 resolution 22]\n"
if water.count(old_cable) != 1:
    raise SystemExit(f'expected one cable_car early rule, got {water.count(old_cable)}')
water = water.replace(old_cable, '', 1)
water = water.replace(
    "# [CUSTOM/АВТОРСКОЕ] Railway/aerialway classes agreed in the completed tag audit.\n",
    "# [CUSTOM/АВТОРСКОЕ] Railway classes agreed in the completed tag audit.\n",
    1,
)
WATER.write_text(water, encoding='utf-8', newline='\n')

typ = TYP.read_text(encoding='utf-8')
for code in ('0x10f01', '0x10f02', '0x10f03', '0x10f04'):
    pattern = re.compile(r'(?ms)^\[_line\]\s*\nType=' + re.escape(code) + r'\s*\n.*?^\[end\]\s*\n')
    matches = list(pattern.finditer(typ))
    if len(matches) != 1:
        raise SystemExit(f'expected one _line {code} section, got {len(matches)}')
    typ = pattern.sub('', typ, count=1)
TYP.write_text(typ, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
pattern = re.compile(
    r"(?ms)^    def test_cable_car_comment_matches_actual_type\(self\) -> None:\n.*?(?=^    def )"
)
matches = list(pattern.finditer(test))
if len(matches) != 1:
    raise SystemExit(f'expected one cable car test method, got {len(matches)}')
new_test = '''    def test_all_aerialways_share_single_visual_type(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        water = WATER_LINES.read_text(encoding='utf-8')\n        typ = (ROOT / 'styles' / 'uralla.txt').read_text(encoding='utf-8')\n        generic = "aerialway=* {name '${name} (${ref})' | '${name}' | '${ref}' } [0x10f15 resolution 22]"\n        self.assertIn(generic, lines)\n        self.assertNotIn('aerialway=cable_car', water)\n        for code in ('0x10f01', '0x10f02', '0x10f03', '0x10f04'):\n            self.assertNotIn(f'Type={code}', typ)\n            self.assertNotIn(code, lines)\n\n'''
test = pattern.sub(new_test, test, count=1)
TEST.write_text(test, encoding='utf-8', newline='\n')

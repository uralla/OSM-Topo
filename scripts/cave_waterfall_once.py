from pathlib import Path
import re

PRIORITY = Path('styles/uralla/inc/priority_points')
TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_cave_waterfall_points.py')

priority = PRIORITY.read_text(encoding='utf-8')
old = "natural=cave_entrance [0x11602 resolution 23]"
new = "natural=cave_entrance { name '${name}' | 'пещера' } [0x11602 resolution 22]"
if priority.count(old) != 1:
    raise SystemExit(f'expected one cave rule, got {priority.count(old)}')
priority = priority.replace(old, new, 1)
PRIORITY.write_text(priority, encoding='utf-8', newline='\n')

typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(r'(?ms)^\[_point\]\nType=0x065\nSubType=0x08\n.*?^\[end\]\n?')
match = pattern.search(typ)
if not match:
    raise SystemExit('waterfall TYP 0x6508 not found')
section = match.group(0)
if 'ExtendedLabels=N' not in section:
    raise SystemExit('expected waterfall ExtendedLabels=N')
section2 = section.replace('ExtendedLabels=N', 'ExtendedLabels=Y\nFontStyle=NoLabel (invisible)', 1)
typ = typ[:match.start()] + section2 + typ[match.end():]
TYP.write_text(typ, encoding='utf-8', newline='\n')

TEST.write_text(r'''from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
TYP = ROOT / 'styles' / 'uralla.txt'

class CaveWaterfallPointTests(unittest.TestCase):
    def test_cave_entrance_uses_custom_cave_symbol_at_topo_zoom(self) -> None:
        text = PRIORITY.read_text(encoding='utf-8')
        self.assertIn("natural=cave_entrance { name '${name}' | 'пещера' } [0x11602 resolution 22]", text)

    def test_waterfall_keeps_icon_but_hides_permanent_label(self) -> None:
        typ = TYP.read_text(encoding='utf-8')
        match = re.search(r'(?ms)^\[_point\]\nType=0x065\nSubType=0x08\n.*?^\[end\]', typ)
        self.assertIsNotNone(match)
        section = match.group(0)
        self.assertIn('ExtendedLabels=Y', section)
        self.assertIn('FontStyle=NoLabel (invisible)', section)
        self.assertNotIn('ExtendedLabels=N', section)

if __name__ == '__main__':
    unittest.main()
''', encoding='utf-8', newline='\n')

from pathlib import Path
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

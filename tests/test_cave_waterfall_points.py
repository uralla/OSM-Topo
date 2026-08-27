from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
TYP = ROOT / 'styles' / 'uralla.txt'

class CaveWaterfallPointTests(unittest.TestCase):
    def test_cave_entrance_visibility_depends_on_name_but_label_is_hidden(self) -> None:
        text = PRIORITY.read_text(encoding='utf-8')
        named = "natural=cave_entrance & name=* { set mkgmap:label:1=' ' } [0x6608 resolution 23]"
        unnamed = "natural=cave_entrance { set mkgmap:label:1=' ' } [0x6608 resolution 24]"
        self.assertIn(named, text)
        self.assertIn(unnamed, text)
        self.assertLess(text.index(named), text.index(unnamed))
        self.assertNotIn("natural=cave_entrance & name=* { name '${name}' } [0x6608 resolution 23]", text)
        self.assertNotIn("natural=cave_entrance { name '${name}' | 'пещера' } [0x6608 resolution 24]", text)

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

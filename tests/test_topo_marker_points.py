from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
LANDUSE = ROOT / 'styles' / 'uralla' / 'inc' / 'landuse_points'
TYP = ROOT / 'styles' / 'uralla.txt'

class TopoMarkerPointTests(unittest.TestCase):
    def test_cairn_and_survey_point_have_dedicated_types(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        landuse = LANDUSE.read_text(encoding='utf-8')
        self.assertIn("man_made=cairn { name '${name}' | 'тура' } [0x11506 resolution 24]", priority)
        self.assertIn('man_made=survey_point {name "${name} (${ele})" | "${name}" | "${ref}" | "геодезический пункт"} [0x11508 resolution 24]', landuse)
        self.assertNotIn('man_made=cairn [0x2f18 resolution 23]', priority)
        self.assertNotIn('man_made=survey_point {name "${name} (${ele})"} [0x6617 resolution 24]', landuse)

        typ = TYP.read_text(encoding='utf-8')
        for subtype in ('0x06', '0x08'):
            pattern = rf"\[_point\]\s*\nType=0x115\s*\nSubType={subtype}\b[\s\S]*?\[end\]"
            match = re.search(pattern, typ)
            self.assertIsNotNone(match, subtype)
            section = match.group(0)
            self.assertIn('ExtendedLabels=Y', section)
            self.assertIn('FontStyle=NoLabel (invisible)', section)

    def test_car_dealer_and_nursing_home_are_not_rendered(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        priority = PRIORITY.read_text(encoding='utf-8')
        self.assertNotIn('amenity=nursing_home', points)
        self.assertNotRegex(priority, r'\bshop=car\b')
        self.assertNotIn('shop=car_dealer', priority)
        self.assertIn('shop=car_parts', priority)
        self.assertIn('shop=car_repair', priority)
        self.assertIn('amenity=car_rental', points)
        self.assertIn('amenity=car_wash', points)

if __name__ == '__main__':
    unittest.main()

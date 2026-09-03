from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
LANDUSE = ROOT / 'styles' / 'uralla' / 'inc' / 'landuse_points'
WATER_POINTS = ROOT / 'styles' / 'uralla' / 'inc' / 'water_points'
TYP = ROOT / 'styles' / 'uralla.txt'

class TopoMarkerPointTests(unittest.TestCase):
    def test_cairn_is_custom_but_survey_point_reuses_0x6617(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        landuse = LANDUSE.read_text(encoding='utf-8')
        self.assertIn("man_made=cairn { name '${name}' | 'тура' } [0x6409 resolution 24]", priority)
        self.assertIn('man_made=survey_point & name=* {name "${name} (${ele})" | "${name}"} [0x6617 resolution 24]', landuse)
        self.assertIn("man_made=survey_point & name!=* { set mkgmap:label:1=' ' } [0x6617 resolution 24]", landuse)
        self.assertNotIn('"геодезический пункт"', landuse)
        self.assertNotIn('0x11508', landuse)
        self.assertNotIn('natural=valley', priority)

        typ = TYP.read_text(encoding='utf-8')
        cairn = re.search(r"\[_point\]\s*\nType=0x066\s*\nSubType=0x0b\b[\s\S]*?\[end\]", typ)
        self.assertIsNotNone(cairn)
        self.assertIn('ExtendedLabels=Y', cairn.group(0))
        self.assertIn('FontStyle=NoLabel (invisible)', cairn.group(0))

        survey_custom = re.search(r"\[_point\]\s*\nType=0x115\s*\nSubType=0x08\b[\s\S]*?\[end\]", typ)
        self.assertIsNone(survey_custom)

    def test_hot_spring_has_only_the_dedicated_rule(self) -> None:
        landuse = LANDUSE.read_text(encoding='utf-8')
        water = WATER_POINTS.read_text(encoding='utf-8')
        self.assertNotIn('natural=hot_spring [0x6511 resolution 22]', landuse)
        self.assertIn(
            'natural=hot_spring & mkgmap:area2poi!=true [0x6416 resolution 22]',
            water,
        )

    def test_car_dealer_and_nursing_home_are_not_rendered(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        priority = PRIORITY.read_text(encoding='utf-8')
        self.assertNotIn('amenity=nursing_home', points)
        self.assertNotRegex(priority, r'\bshop=car\b')
        self.assertNotIn('shop=car_dealer', priority)
        self.assertIn('shop=car_parts', priority)
        self.assertIn('shop=car_repair', priority)
        self.assertNotIn('amenity=car_rental', points)
        self.assertIn(
            '(amenity=car_rental | amenity=car_sharing | shop=car_rental) [0x2f0d resolution 24]',
            priority,
        )
        self.assertIn('amenity=car_wash', points)

if __name__ == '__main__':
    unittest.main()

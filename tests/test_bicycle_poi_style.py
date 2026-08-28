from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'
PLACE_POINTS = ROOT / 'styles' / 'uralla' / 'inc' / 'place_points'
TYP = ROOT / 'styles' / 'uralla.txt'


class BicyclePoiStyleTests(unittest.TestCase):
    def test_bicycle_shop_and_repair_station_use_dedicated_type(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        points = POINTS.read_text(encoding='utf-8')

        self.assertIn(
            "shop=bicycle { name '${name}' | 'велосипеды' } [0x1150a resolution 23]",
            priority,
        )
        self.assertIn(
            "amenity=bicycle_repair_station { name '${name}' | 'велосипеды' } [0x1150a resolution 24]",
            priority,
        )
        self.assertNotRegex(priority, r'shop=bicycle[^\n]*0x2f0d')
        self.assertNotRegex(priority, r'amenity=bicycle_repair_station[^\n]*0x2f0d')
        self.assertNotIn('amenity=car_club', priority)
        self.assertNotIn('amenity=car_club', points)

    def test_bicycle_typ_is_visible_small_white_circle(self) -> None:
        typ = TYP.read_text(encoding='utf-8')
        match = re.search(
            r'(?ms)^\[_point\]\nType=0x115\nSubType=0x0a\n.*?^\[end\]',
            typ,
        )
        self.assertIsNotNone(match)
        section = match.group(0)

        self.assertIn('String1=0x19,велосипеды', section)
        self.assertIn('String2=0x04,bicycle', section)
        self.assertIn('ExtendedLabels=Y', section)
        self.assertIn('FontStyle=SmallFont', section)
        self.assertNotIn('NoLabel', section)
        self.assertIn('"!\tc #000000"', section)
        self.assertIn('"#\tc #FFFFFF"', section)
        self.assertIn('" \tc none"', section)
        self.assertNotIn(r'\tc ', section)
        self.assertIn('"   !!!!!   "', section)
        self.assertIn('"!#########!"', section)

    def test_car_rental_and_sharing_keep_2f0d(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        self.assertIn(
            '(amenity=car_rental | amenity=car_sharing | shop=car_rental) [0x2f0d resolution 24]',
            priority,
        )

        typ = TYP.read_text(encoding='utf-8')
        match = re.search(
            r'(?ms)^\[_point\]\nType=0x02f\nSubType=0x0d\n.*?^\[end\]',
            typ,
        )
        self.assertIsNotNone(match)

    def test_locality_keeps_urrochische_type_11504(self) -> None:
        place_style = PLACE_POINTS.read_text(encoding='utf-8')
        self.assertIn(
            'place=locality & mkgmap:area2poi!=true          [0x11504 resolution 24]',
            place_style,
        )

        typ = TYP.read_text(encoding='utf-8')
        match = re.search(r'(?ms)^\[_point\]\nType=0x115\nSubType=0x04\n.*?^\[end\]', typ)
        self.assertIsNotNone(match)
        section = match.group(0)
        self.assertIn('String1=0x19,урочище', section)
        self.assertIn('FontStyle=NoLabel (invisible)', section)


if __name__ == '__main__':
    unittest.main()

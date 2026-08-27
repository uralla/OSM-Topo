from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
PLACE_POINTS = ROOT / 'styles' / 'uralla' / 'inc' / 'place_points'
TYP = ROOT / 'styles' / 'uralla.txt'


class BicyclePoiStyleTests(unittest.TestCase):
    def test_bicycle_shop_and_repair_station_reuse_2f0d(self) -> None:
        style = PRIORITY.read_text(encoding='utf-8')
        self.assertIn('shop=bicycle [0x2f0d resolution 23]', style)
        self.assertIn('amenity=bicycle_repair_station [0x2f0d resolution 24]', style)
        self.assertIn('amenity=car_club [0x2f03 resolution 24]', style)
        self.assertNotIn('shop=bicycle [0x11504', style)
        self.assertNotIn('amenity=bicycle_repair_station [0x11504', style)
        self.assertNotIn('0x2f13', style)
        self.assertNotIn('0x11509', style)

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

    def test_2f0d_exists_in_typ(self) -> None:
        typ = TYP.read_text(encoding='utf-8')
        match = re.search(r'(?ms)^\[_point\]\nType=0x02f\nSubType=0x0d\n.*?^\[end\]', typ)
        self.assertIsNotNone(match)


if __name__ == '__main__':
    unittest.main()

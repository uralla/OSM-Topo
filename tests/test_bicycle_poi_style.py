from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
TYP = ROOT / 'styles' / 'uralla.txt'


class BicyclePoiStyleTests(unittest.TestCase):
    def test_bicycle_shop_and_repair_station_use_existing_custom_type(self) -> None:
        style = PRIORITY.read_text(encoding='utf-8')
        self.assertIn('shop=bicycle [0x11504 resolution 23]', style)
        self.assertIn('amenity=bicycle_repair_station [0x11504 resolution 24]', style)
        self.assertNotIn('0x2f13', style)
        self.assertNotIn('0x11509', style)

    def test_custom_type_11504_exists_in_typ(self) -> None:
        typ = TYP.read_text(encoding='utf-8')
        match = re.search(r'(?ms)^\[_point\]\nType=0x115\nSubType=0x04\n.*?^\[end\]', typ)
        self.assertIsNotNone(match)
        self.assertIn('FontStyle=NoLabel (invisible)', match.group(0))


if __name__ == '__main__':
    unittest.main()

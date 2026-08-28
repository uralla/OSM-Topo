from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'
TYP = ROOT / 'styles' / 'uralla.txt'


class PicnicTableStyleTests(unittest.TestCase):
    def test_picnic_table_uses_close_zoom_small_rest_icon(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        self.assertIn('leisure=picnic_table [0x4a01 resolution 24]', priority)

    def test_4a01_is_existing_hidden_label_small_rest_type(self) -> None:
        typ = TYP.read_text(encoding='utf-8')
        match = re.search(r'(?ms)^\[_point\]\nType=0x04a\nSubType=0x01\n.*?^\[end\]', typ)
        self.assertIsNotNone(match)
        self.assertIn('FontStyle=NoLabel (invisible)', match.group(0))

    def test_existing_picnic_site_and_bench_semantics_remain_separate(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn('tourism=picnic_site & shelter=yes [0x2b05 resolution 24]', points)
        self.assertIn('tourism=picnic_site & shelter!=yes [0x4a00 resolution 24]', points)
        self.assertIn('amenity=bench [0x4a01 resolution 24]', points)
        self.assertNotIn('leisure=picnic_table', points)


if __name__ == '__main__':
    unittest.main()

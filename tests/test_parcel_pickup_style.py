from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'
TYP = ROOT / 'styles' / 'uralla.txt'


class ParcelPickupStyleTests(unittest.TestCase):
    def test_pickup_tags_share_post_office_type(self) -> None:
        style = PRIORITY.read_text(encoding='utf-8')
        rule = "(amenity=parcel_locker | post_office=post_partner | shop=outpost | amenity=vending_machine & vending~'.*parcel_pickup.*') { name '${name}' | 'пункт выдачи' } [0x2f05 resolution 24]"
        self.assertIn(rule, style)
        self.assertNotIn("'${brand}'", rule)
        self.assertNotIn("'${operator}'", rule)
        self.assertNotIn("'${ref}'", rule)

    def test_existing_post_office_keeps_same_type(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn('amenity=post_office [0x2f05 resolution 24]', points)

    def test_post_office_type_uses_visible_small_font(self) -> None:
        typ = TYP.read_text(encoding='utf-8')
        match = re.search(r'(?ms)^\[_point\]\nType=0x02f\nSubType=0x05\n.*?^\[end\]', typ)
        self.assertIsNotNone(match)
        section = match.group(0)
        self.assertIn('String1=0x19,почта', section)
        self.assertIn('ExtendedLabels=Y', section)
        self.assertIn('FontStyle=SmallFont', section)
        self.assertNotIn('FontStyle=NoLabel (invisible)', section)


if __name__ == '__main__':
    unittest.main()

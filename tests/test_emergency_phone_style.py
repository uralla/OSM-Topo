from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'

class EmergencyPhoneStyleTests(unittest.TestCase):
    def test_emergency_phone_is_visible_before_ordinary_telephone(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn("emergency=phone [0x2f12 resolution 23]", points)
        self.assertIn("amenity=telephone [0x2f12 resolution 24]", points)
        self.assertLess(points.index("emergency=phone [0x2f12 resolution 23]"), points.index("amenity=telephone [0x2f12 resolution 24]"))

if __name__ == '__main__':
    unittest.main()

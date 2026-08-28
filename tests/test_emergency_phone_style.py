from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class EmergencyPhoneStyleTests(unittest.TestCase):
    def test_emergency_phone_and_ordinary_telephone_are_separated(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        points = POINTS.read_text(encoding='utf-8')

        self.assertIn(
            '(amenity=emergency_phone | emergency=phone) [0x2f12 resolution 23]',
            priority,
        )
        self.assertIn('amenity=telephone [0x2f12 resolution 24]', points)

        active_points = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )
        self.assertNotIn('emergency=phone [0x2f12 resolution 23]', active_points)


if __name__ == '__main__':
    unittest.main()

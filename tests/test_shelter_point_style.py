from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class ShelterPointStyleTests(unittest.TestCase):
    def test_standard_shelter_and_legacy_lean_to_use_existing_shelter_icon(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn(
            'amenity=shelter & mkgmap:area2poi!=true [0x2b05 resolution 23]',
            priority,
        )
        self.assertIn('tourism=lean_to [0x2b05 resolution 24]', points)
        self.assertNotIn('amenity=shelter | tourism=lean_to', points)


if __name__ == '__main__':
    unittest.main()

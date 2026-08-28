from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class AirportPointStyleTests(unittest.TestCase):
    def test_airport_compatibility_tags_share_one_rule(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        active = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )

        unified = '(aeroway=aerodrome | aeroway=airport | amenity=airport) [0x2f04 resolution 19]'
        self.assertIn(unified, active)
        stripped = active.replace(unified, '')
        self.assertNotIn('aeroway=aerodrome [0x2f04 resolution 19]', stripped)
        self.assertNotIn('aeroway=airport [0x2f04 resolution 19]', stripped)
        self.assertNotIn('amenity=airport [0x2f04 resolution 19]', stripped)

    def test_terminal_and_helipad_keep_separate_rules(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn('aeroway=helipad [0x11803 resolution 23]', points)
        self.assertIn('aeroway=terminal [0x2f04 resolution 22]', points)


if __name__ == '__main__':
    unittest.main()

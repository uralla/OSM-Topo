from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class MuseumPointStyleTests(unittest.TestCase):
    def test_historic_and_tourism_museum_share_one_rule(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        active_points = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )

        # Current and legacy museum tags must render identically through one rule.
        unified = '(historic=museum | tourism=museum) [0x2c02 resolution 24]'
        self.assertIn(unified, active_points)
        self.assertNotIn('historic=museum [0x2c02 resolution 24]', active_points.replace(unified, ''))
        self.assertNotIn('tourism=museum [0x2c02 resolution 24]', active_points.replace(unified, ''))


if __name__ == '__main__':
    unittest.main()

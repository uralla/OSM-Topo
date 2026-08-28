from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class FortCastlePointStyleTests(unittest.TestCase):
    def test_fort_and_castle_share_resolution_22_rule(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        active_points = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )

        unified = '(historic=fort | historic=castle) [0x11604 resolution 22]'
        self.assertIn(unified, active_points)
        self.assertNotIn('historic=fort [0x11604 resolution 21]', active_points)
        self.assertNotIn('historic=castle [0x11604 resolution 21]', active_points)


if __name__ == '__main__':
    unittest.main()

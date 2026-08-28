from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class SupermarketPointStyleTests(unittest.TestCase):
    def test_current_and_legacy_supermarket_tags_share_resolution_23(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        points = POINTS.read_text(encoding='utf-8')

        self.assertIn(
            '(shop=supermarket | amenity=supermarket) [0x2e02 resolution 23]',
            priority,
        )

        active_points = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )
        self.assertNotIn('amenity=supermarket [', active_points)
        self.assertNotIn('shop=supermarket [', active_points)


if __name__ == '__main__':
    unittest.main()

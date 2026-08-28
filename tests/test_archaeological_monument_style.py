from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class ArchaeologicalMonumentStyleTests(unittest.TestCase):
    def test_archaeological_site_and_monument_share_one_rule(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        active_points = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )

        unified = '(historic=archaeological_site | historic=monument) [0x2c04 resolution 24]'
        self.assertIn(unified, active_points)
        without_unified = active_points.replace(unified, '')
        self.assertNotIn('historic=archaeological_site [0x2c04 resolution 24]', without_unified)
        self.assertNotIn('historic=monument [0x2c04 resolution 24]', without_unified)


if __name__ == '__main__':
    unittest.main()

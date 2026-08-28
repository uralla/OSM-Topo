from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class HutPointStyleTests(unittest.TestCase):
    def test_alpine_and_wilderness_huts_are_rendered_by_priority_rule(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn(
            '(tourism=wilderness_hut | tourism=alpine_hut) [0x2b07 resolution 23]',
            priority,
        )
        self.assertIn('tourism=lean_to [0x2b05 resolution 24]', points)


if __name__ == '__main__':
    unittest.main()

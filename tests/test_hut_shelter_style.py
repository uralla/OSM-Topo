from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
POINTS = ROOT / 'styles' / 'uralla' / 'points'


def active_style(text: str) -> str:
    return '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))


class HutShelterStyleTests(unittest.TestCase):
    def test_huts_are_defined_only_in_priority_points(self) -> None:
        priority = active_style(PRIORITY.read_text(encoding='utf-8'))
        points = active_style(POINTS.read_text(encoding='utf-8'))

        self.assertIn(
            '(tourism=wilderness_hut | tourism=alpine_hut) [0x2b07 resolution 23]',
            priority,
        )
        self.assertNotIn('tourism=wilderness_hut [', points)
        self.assertNotIn('tourism=alpine_hut [', points)

    def test_shelter_and_legacy_lean_to_are_separated(self) -> None:
        priority = active_style(PRIORITY.read_text(encoding='utf-8'))
        points = active_style(POINTS.read_text(encoding='utf-8'))

        self.assertIn(
            'amenity=shelter & mkgmap:area2poi!=true [0x2b05 resolution 23]',
            priority,
        )
        self.assertIn('tourism=lean_to [0x2b05 resolution 24]', points)
        self.assertNotIn('amenity=shelter | tourism=lean_to', points)


if __name__ == '__main__':
    unittest.main()

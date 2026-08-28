from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class ZooPointStyleTests(unittest.TestCase):
    def test_legacy_and_current_zoo_tags_share_one_rule(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        active = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )

        self.assertIn(
            '(amenity=zoo | tourism=zoo) [0x2c07 resolution 24]',
            active,
        )
        self.assertNotIn('\namenity=zoo [0x2c07 resolution 24]', '\n' + active)
        self.assertNotIn('\ntourism=zoo [0x2c07 resolution 24]', '\n' + active)


if __name__ == '__main__':
    unittest.main()

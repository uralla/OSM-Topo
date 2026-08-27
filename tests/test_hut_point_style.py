from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'

class HutPointStyleTests(unittest.TestCase):
    def test_alpine_and_wilderness_huts_are_rendered(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn("tourism=alpine_hut [0x2b02 resolution 21]", points)
        self.assertIn("tourism=wilderness_hut [0x2b05 resolution 23]", points)
        self.assertIn("amenity=shelter | tourism=lean_to [0x2b05 resolution 24]", points)

if __name__ == '__main__':
    unittest.main()

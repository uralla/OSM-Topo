from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'

class ShelterPointStyleTests(unittest.TestCase):
    def test_standard_osm_shelter_uses_existing_shelter_icon(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn("amenity=shelter | tourism=lean_to [0x2b05 resolution 24]", points)
        self.assertNotIn("tourism=lean_to [0x2b05 resolution 24]", points.replace("amenity=shelter | tourism=lean_to [0x2b05 resolution 24]", ""))
        self.assertNotIn("tourism=lean_to replaces some uses of amenity=shelter", points)

if __name__ == '__main__':
    unittest.main()

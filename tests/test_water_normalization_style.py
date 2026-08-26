from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WATER_POLYGONS = ROOT / 'styles' / 'uralla' / 'inc' / 'water_polygons'
LANDUSE_POLYGONS = ROOT / 'styles' / 'uralla' / 'inc' / 'landuse_polygons'


class WaterNormalizationStyleTests(unittest.TestCase):
    def test_reservoir_is_normalized_once_into_natural_water(self) -> None:
        water = WATER_POLYGONS.read_text(encoding='utf-8')
        landuse = LANDUSE_POLYGONS.read_text(encoding='utf-8')
        self.assertIn('landuse=reservoir & mkgmap:area2poi!=true', water)
        self.assertIn('{add natural=water}', water)
        self.assertNotIn('landuse=reservoir & natural!=*', landuse)

    def test_old_commented_water_alternatives_are_gone(self) -> None:
        water = WATER_POLYGONS.read_text(encoding='utf-8')
        self.assertNotIn('#(landuse=reservoir | water=reservoir)', water)
        self.assertNotIn('#natural=bay [0x3d', water)
        self.assertNotIn('# natural=water [0x3c', water)


if __name__ == '__main__':
    unittest.main()

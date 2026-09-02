from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLYGONS = ROOT / "styles" / "uralla" / "polygons"


class PolygonPrecedenceStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLYGONS.read_text(encoding="utf-8")

    def test_fuel_area_is_not_consumed_by_generic_shop_polygon(self) -> None:
        shop_rule = "shop=* & building!=* [0x08 resolution 21]"
        fuel_rule = "amenity=fuel & building!=* [0x10f0c resolution 24]"
        self.assertIn(shop_rule, self.text)
        self.assertIn(fuel_rule, self.text)
        self.assertLess(self.text.index(fuel_rule), self.text.index(shop_rule))

    def test_legacy_swimming_pool_normalizes_to_rendered_leisure_polygon(self) -> None:
        normalize = "amenity=swimming_pool & leisure!=* { add leisure=swimming_pool }"
        sport = "leisure=swimming_pool { set sport=swimming }"
        render = "leisure=swimming_pool { name '${name}' | '${addr:street} ${addr:housenumber}'"
        self.assertIn(normalize, self.text)
        self.assertIn(sport, self.text)
        self.assertIn(render, self.text)
        self.assertLess(self.text.index(normalize), self.text.index(sport))
        self.assertLess(self.text.index(sport), self.text.index(render))
        self.assertNotIn("leisure=swimming_pool | amenity=swimming_pool {set sport=swimming}", self.text)

    def test_private_leisure_catchall_is_absent(self) -> None:
        reserve = (
            "(leisure=nature_reserve | leisure=natural_reserve | "
            "landuse=nature_reserve | landuse=natural_reserve)\n"
            "    & area_size()>50000 & boundary!=protected_area & boundary!=national_park\n"
            "    [0x16 resolution 19-22 continue]"
        )
        self.assertIn(reserve, self.text)
        self.assertNotIn("leisure=* & access=private", self.text)


if __name__ == "__main__":
    unittest.main()

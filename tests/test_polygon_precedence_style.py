from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLYGONS = ROOT / "styles" / "uralla" / "polygons"


class PolygonPrecedenceStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLYGONS.read_text(encoding="utf-8")

    def test_fuel_area_is_not_consumed_by_generic_shop_polygon(self) -> None:
        shop_rule = "shop=* & building!=* & amenity!=fuel [0x08 resolution 21]"
        fuel_rule = "amenity=fuel & area=yes [0x10f0c resolution 24]"
        self.assertIn(shop_rule, self.text)
        self.assertIn(fuel_rule, self.text)
        self.assertNotIn("shop=* & building!=* [0x08 resolution 21]", self.text)

    def test_legacy_swimming_pool_normalizes_to_rendered_leisure_polygon(self) -> None:
        normalize = "amenity=swimming_pool & leisure!=* { add leisure=swimming_pool }"
        sport = "leisure=swimming_pool { set sport=swimming }"
        render = "leisure=swimming_pool { name '${addr:street} ${addr:housenumber} (${name})'"
        self.assertIn(normalize, self.text)
        self.assertIn(sport, self.text)
        self.assertIn(render, self.text)
        self.assertLess(self.text.index(normalize), self.text.index(sport))
        self.assertLess(self.text.index(sport), self.text.index(render))
        self.assertNotIn("leisure=swimming_pool | amenity=swimming_pool {set sport=swimming}", self.text)

    def test_private_nature_reserve_does_not_regain_close_zoom_fill(self) -> None:
        reserve = (
            "leisure=nature_reserve & area_size()>50000 | "
            "leisure=natural_reserve & area_size()>50000 | "
            "landuse=nature_reserve & area_size()>50000 | "
            "landuse=natural_reserve & area_size()>50000 "
            "[0x16 resolution 19-22 continue]"
        )
        private_fallback = (
            "leisure=* & access=private & leisure!=nature_reserve "
            "& leisure!=natural_reserve [0x19 resolution 23]"
        )
        self.assertIn(reserve, self.text)
        self.assertIn(private_fallback, self.text)
        self.assertNotIn("leisure=* & access=private [0x19 resolution 23]", self.text)
        self.assertLess(self.text.index(reserve), self.text.index(private_fallback))


if __name__ == "__main__":
    unittest.main()

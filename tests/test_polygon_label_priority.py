from pathlib import Path
import unittest


POLYGONS = Path(__file__).resolve().parents[1] / "styles" / "uralla" / "polygons"


class PolygonLabelPriorityTests(unittest.TestCase):
    def test_named_polygons_prefer_real_name_over_address(self) -> None:
        text = POLYGONS.read_text(encoding="utf-8")
        self.assertNotIn("'${addr:street} ${addr:housenumber} (${name})'", text)

        name_first = "name '${name}' | '${addr:street} ${addr:housenumber}' | '${addr:housenumber}'"
        self.assertGreaterEqual(text.count(name_first), 6)

    def test_generic_polygon_fallbacks_do_not_overwrite_real_names(self) -> None:
        text = POLYGONS.read_text(encoding="utf-8")
        for rule in (
            "leisure=dog_park { name '${name}' | 'площадка для собак' }",
            "{ name '${name}' | 'платформа' } [0x10f14 resolution 21]",
        ):
            self.assertIn(rule, text)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest

from uralla_build.poi_context_analysis import (
    SCHEMA_VERSION,
    _is_small_settlement,
)


ROOT = Path(__file__).resolve().parents[1]
PLACE_POINTS = ROOT / "styles" / "uralla" / "inc" / "place_points"


class SettlementDensityLodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = PLACE_POINTS.read_text(encoding="utf-8")

    def test_poi_context_schema_bumped_for_settlement_density(self) -> None:
        self.assertEqual(SCHEMA_VERSION, 4)

    def test_named_small_settlement_classes_are_adaptive(self) -> None:
        for place in ("village", "hamlet", "isolated_dwelling", "locality", "farm"):
            self.assertTrue(_is_small_settlement({"place": place, "name": "Контроль"}))
        self.assertFalse(_is_small_settlement({"place": "locality"}))
        self.assertFalse(_is_small_settlement({"place": "town", "name": "Городок"}))

    def test_sparse_small_settlements_can_start_at_resolution_19(self) -> None:
        self.assertIn(
            "place=village & mkgmap:area2poi!=true & uralla:poi_screen_pressure=low [0x0a00 resolution 19]",
            self.text,
        )
        self.assertIn(
            "place=hamlet & mkgmap:area2poi!=true & uralla:poi_screen_pressure=low [0x0b00 resolution 19]",
            self.text,
        )
        self.assertIn(
            "(place=isolated_dwelling | place=farm) & mkgmap:area2poi!=true & uralla:poi_screen_pressure=low [0x0b00 resolution 19]",
            self.text,
        )
        self.assertIn(
            "place=locality & name=* & mkgmap:area2poi!=true & uralla:poi_screen_pressure=low { name '${name}' } [0x6408 resolution 19]",
            self.text,
        )

    def test_dense_context_defers_less_significant_places(self) -> None:
        self.assertIn(
            "place=village & mkgmap:area2poi!=true & uralla:poi_screen_pressure=high [0x0a00 resolution 21]",
            self.text,
        )
        self.assertIn(
            "place=hamlet & mkgmap:area2poi!=true & uralla:poi_screen_pressure=high [0x0b00 resolution 21]",
            self.text,
        )
        self.assertIn(
            "(place=isolated_dwelling | place=farm) & mkgmap:area2poi!=true & uralla:poi_screen_pressure=high [0x0b00 resolution 22]",
            self.text,
        )
        self.assertIn(
            "place=locality & name=* & mkgmap:area2poi!=true & uralla:poi_screen_pressure=high { name '${name}' } [0x6408 resolution 23]",
            self.text,
        )

    def test_population_can_promote_within_dense_context(self) -> None:
        self.assertIn(
            "place=village & mkgmap:area2poi!=true & population > 4999 [0x0900 resolution 19]",
            self.text,
        )
        self.assertIn(
            "place=village & mkgmap:area2poi!=true & population > 999 & uralla:poi_screen_pressure=high [0x0900 resolution 20]",
            self.text,
        )
        self.assertIn(
            "place=hamlet & mkgmap:area2poi!=true & population > 999 [0x0b00 resolution 19]",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

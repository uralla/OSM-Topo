from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / "styles" / "uralla" / "inc" / "priority_points"
RELIEF = ROOT / "styles" / "uralla" / "inc" / "landuse_points"


class MountainPassStyleTests(unittest.TestCase):
    def test_generic_saddle_does_not_consume_mountain_pass(self) -> None:
        text = PRIORITY.read_text(encoding="utf-8")
        self.assertIn("natural=saddle & mountain_pass!=yes [0x11507 resolution 23]", text)
        self.assertNotIn("\nnatural=saddle [0x11507 resolution 23]", text)

    def test_detailed_mountain_pass_rule_keeps_rich_labels(self) -> None:
        text = RELIEF.read_text(encoding="utf-8")
        self.assertIn("mountain_pass=yes {name", text)
        self.assertIn("${rtsa_scale}", text)
        self.assertIn("${pass:category}", text)
        self.assertIn("[0x11507 resolution 23]", text)

    def test_elevation_fallback_does_not_consume_mountain_pass(self) -> None:
        text = RELIEF.read_text(encoding="utf-8")
        self.assertIn(
            'ele=* & natural!=* & mountain_pass!=yes {name "${ele} м"} [0x6405 resolution 24]',
            text,
        )
        self.assertNotIn(
            'ele=* & natural!=* {name "${ele} м"} [0x6405 resolution 24]',
            text,
        )

    def test_generic_building_is_final_point_fallback(self) -> None:
        priority = PRIORITY.read_text(encoding="utf-8")
        relief = RELIEF.read_text(encoding="utf-8")
        building = "(building=yes | building=true) & mkgmap:area2poi!=true [0x6402 resolution 24]"
        self.assertNotIn(building, priority)
        self.assertIn(building, relief)
        self.assertGreater(relief.index(building), relief.index("mountain_pass=yes {name"))


if __name__ == "__main__":
    unittest.main()

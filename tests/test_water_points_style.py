from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WATER_POINTS = ROOT / "styles" / "uralla" / "inc" / "water_points"


class WaterPointsStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WATER_POINTS.read_text(encoding="utf-8")

    def test_stream_is_a_waterway_line_not_a_natural_point(self) -> None:
        self.assertNotIn("natural=stream", self.text)

    def test_area_natural_features_do_not_create_duplicate_area2poi_icons(self) -> None:
        for fragment in (
            "natural=beach & mkgmap:area2poi!=true [0x6604",
            "natural=glacier & mkgmap:area2poi!=true [0x650a",
            "natural=water & name=* & mkgmap:area2poi!=true [0x6603",
            "& name=* & mkgmap:area2poi!=true [0x6513",
        ):
            self.assertIn(fragment, self.text)

    def test_glacier_native_garmin_type_is_intentional(self) -> None:
        self.assertIn("0x650a intentionally uses the native Garmin symbol", self.text)

    def test_water_source_classes_are_preserved(self) -> None:
        self.assertIn("[0x6511 resolution 22]", self.text)
        self.assertIn("[0x6512 resolution 23]", self.text)
        self.assertIn("[0x5001 resolution 23]", self.text)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLYGONS = ROOT / "styles/uralla/polygons"


class FootwayPolygonStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = POLYGONS.read_text(encoding="utf-8")

    def test_area_footway_uses_pedestrian_area_polygon(self) -> None:
        self.assertIn(
            "highway=footway & (area=yes | mkgmap:mp_created=true)",
            self.text,
        )
        self.assertIn("[0x10f12 resolution 21]", self.text)
        self.assertNotIn("[0x0d resolution 21]", self.text)

    def test_generic_highway_area_is_not_forced_to_parking(self) -> None:
        self.assertNotIn(
            "highway=* & (area=yes | mkgmap:mp_created=true) [0x05 resolution 21]",
            self.text,
        )

    def test_real_parking_still_uses_0x05(self) -> None:
        self.assertIn(
            "amenity=parking | parking=surface [0x05 resolution 24]",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

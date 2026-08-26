from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLACE_POINTS = REPO_ROOT / "styles" / "uralla" / "inc" / "place_points"
OPTIONS = REPO_ROOT / "styles" / "uralla" / "options"


class PlacePointsStyleTests(unittest.TestCase):
    def test_city_population_thresholds_are_stable(self) -> None:
        text = PLACE_POINTS.read_text(encoding="utf-8")
        expected = (
            "place=city & mkgmap:area2poi!=true & population > 999999 [0x0100 resolution 12]",
            "place=city & mkgmap:area2poi!=true & population > 499999 [0x0200 resolution 14]",
            "place=city & mkgmap:area2poi!=true & population > 249999 [0x0400 resolution 15]",
            "place=city & mkgmap:area2poi!=true & population > 99999  [0x0600 resolution 16]",
            "place=city & mkgmap:area2poi!=true & population > 49999  [0x0700 resolution 17]",
            "place=city & mkgmap:area2poi!=true & population > 0      [0x0800 resolution 18]",
        )
        for rule in expected:
            self.assertIn(rule, text)

    def test_resolution_15_is_an_intentional_threshold(self) -> None:
        options = OPTIONS.read_text(encoding="utf-8")
        self.assertIn("overview-levels = 8:16, 9:14, 10:12", options)
        self.assertIn("population > 249999 [0x0400 resolution 15]", PLACE_POINTS.read_text(encoding="utf-8"))

    def test_small_settlements_stay_close_zoom(self) -> None:
        text = PLACE_POINTS.read_text(encoding="utf-8")
        self.assertIn("place=hamlet & mkgmap:area2poi!=true            [0x0b00 resolution 22]", text)
        self.assertIn("place=isolated_dwelling & mkgmap:area2poi!=true [0x0b00 resolution 23]", text)
        self.assertIn("place=locality & mkgmap:area2poi!=true          [0x11504 resolution 24]", text)


if __name__ == "__main__":
    unittest.main()

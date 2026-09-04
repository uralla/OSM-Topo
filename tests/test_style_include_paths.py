from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StyleIncludePathTests(unittest.TestCase):
    def test_place_points_uses_style_root_path_for_peak_priority(self):
        style = (ROOT / "styles/uralla/inc/place_points").read_text(encoding="utf-8")
        self.assertIn("include 'inc/peak_priority';", style)
        self.assertNotIn("include 'peak_priority';", style)

    def test_peak_priority_precedes_generic_priority_points(self):
        points = (ROOT / "styles/uralla/points").read_text(encoding="utf-8")
        place_pos = points.index("include 'inc/place_points';")
        generic_pos = points.index("include 'inc/priority_points';")
        self.assertLess(place_pos, generic_pos)


if __name__ == "__main__":
    unittest.main()

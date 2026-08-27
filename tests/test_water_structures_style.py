from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WATER_LINES = REPO_ROOT / "styles" / "uralla" / "inc" / "water_lines"
WATER_POLYGONS = REPO_ROOT / "styles" / "uralla" / "inc" / "water_polygons"
POLYGONS = REPO_ROOT / "styles" / "uralla" / "polygons"


class WaterStructuresStyleTests(unittest.TestCase):
    def test_closed_water_structures_use_pier_polygon_class(self) -> None:
        lines = WATER_LINES.read_text(encoding="utf-8")
        polygons = POLYGONS.read_text(encoding="utf-8")
        self.assertIn(
            "(man_made=pier | man_made=breakwater | man_made=groyne | man_made=quay) & is_closed()=true { set uralla:pier_polygon=yes; delete man_made }",
            lines,
        )
        self.assertIn(
            "(man_made=pier | man_made=breakwater) [0x10f11 resolution 24]",
            polygons,
        )
        self.assertLess(
            polygons.index("(man_made=pier | man_made=breakwater) [0x10f11 resolution 24]"),
            polygons.index("\nman_made=* & area=yes"),
        )

    def test_open_breakwater_uses_pier_line_class(self) -> None:
        lines = WATER_LINES.read_text(encoding="utf-8")
        self.assertIn(
            "man_made=breakwater & is_closed()=false & area!=yes { name '${name}' | 'волнорез'; set uralla:pier_rendered=yes } [0x10f07 resolution 24 continue]",
            lines,
        )

    def test_pier_polygon_marker_is_still_consumed(self) -> None:
        self.assertIn(
            "uralla:pier_polygon=yes [0x10f11 resolution 24]",
            WATER_POLYGONS.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()

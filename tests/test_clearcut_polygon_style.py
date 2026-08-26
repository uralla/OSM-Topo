from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLYGONS = ROOT / "styles" / "uralla" / "polygons"
LANDUSE = ROOT / "styles" / "uralla" / "inc" / "landuse_polygons"


class ClearcutPolygonStyleTests(unittest.TestCase):
    def test_legacy_and_current_clearcuts_normalize_to_scrub(self) -> None:
        text = POLYGONS.read_text(encoding="utf-8")
        normalize = "(man_made=clearcut | landuse=logging) { add natural=scrub }"
        self.assertIn(normalize, text)
        self.assertNotIn("(man_made=clearcut | landuse=logging) {add natural=heath}", text)
        self.assertLess(text.index(normalize), text.index("man_made=* & natural=* {delete man_made}"))
        self.assertLess(text.index(normalize), text.index("include 'inc/landuse_polygons';"))

    def test_clearcut_has_one_scrub_rendering_branch(self) -> None:
        text = LANDUSE.read_text(encoding="utf-8")
        self.assertIn("natural=scrub [0x1321e resolution 21-23 continue]", text)
        self.assertIn("natural=scrub [0x4f resolution 24]", text)
        self.assertNotIn("man_made=clearcut", text)
        self.assertNotIn("landuse=logging", text)


if __name__ == "__main__":
    unittest.main()

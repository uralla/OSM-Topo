from pathlib import Path
import unittest

from uralla_build.poi_context_analysis import _is_adaptive


ROOT = Path(__file__).resolve().parents[1]


class AntennaLodTests(unittest.TestCase):
    def test_antenna_is_adaptive_but_mast_is_not(self):
        self.assertTrue(_is_adaptive({"man_made": "antenna"}))
        self.assertFalse(_is_adaptive({"man_made": "mast"}))

    def test_point_style_uses_full_hml_range_for_antenna(self):
        style = (ROOT / "styles/uralla/inc/priority_points").read_text(encoding="utf-8")
        self.assertIn(
            "uralla:poi_lod_class=H & man_made=antenna [0x641c resolution 22]",
            style,
        )
        self.assertIn(
            "uralla:poi_lod_class=M & man_made=antenna [0x641c resolution 23]",
            style,
        )
        self.assertIn(
            "uralla:poi_lod_class=L & man_made=antenna [0x641c resolution 24]",
            style,
        )

    def test_industrial_fallback_is_compact(self):
        style = (ROOT / "styles/uralla/inc/landuse_polygons").read_text(encoding="utf-8")
        self.assertIn(
            "landuse=industrial { name '${name}' | 'промзона' } [0x0c resolution 21]",
            style,
        )
        self.assertNotIn("промышленная зона", style)


if __name__ == "__main__":
    unittest.main()

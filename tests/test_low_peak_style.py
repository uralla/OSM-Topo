from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LANDUSE = ROOT / "styles" / "uralla" / "inc" / "landuse_points"


class LowPeakStyleTests(unittest.TestCase):
    def test_peak_and_hill_below_200m_use_only_6615(self):
        text = LANDUSE.read_text(encoding="utf-8")
        rule = "(natural=peak | natural=hill) & ele < 200 [0x6615 resolution 24]"
        self.assertIn(rule, text)
        self.assertLess(text.index(rule), text.index("natural=peak & ele=* & name=*"))
        self.assertNotIn("(natural=peak | natural=hill) & ele < 200 [0x6615 resolution 23", text)


if __name__ == "__main__":
    unittest.main()

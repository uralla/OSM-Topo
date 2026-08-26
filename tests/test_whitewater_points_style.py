from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "styles" / "uralla" / "points"


class WhitewaterPointsStyleTests(unittest.TestCase):
    def test_combined_put_in_egress_precedes_single_rules(self) -> None:
        text = POINTS.read_text(encoding="utf-8")
        combined = "whitewater=put_in & whitewater=egress [0x6516 resolution 24]"
        egress = "whitewater=egress\t  [0x6514 resolution 24]"
        put_in = "whitewater=put_in\t  [0x6515 resolution 24]"
        self.assertIn(combined, text)
        self.assertIn(egress, text)
        self.assertIn(put_in, text)
        self.assertLess(text.index(combined), text.index(egress))
        self.assertLess(text.index(combined), text.index(put_in))


if __name__ == "__main__":
    unittest.main()

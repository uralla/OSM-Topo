from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"


class CliffTypOrientationTests(unittest.TestCase):
    def test_directional_slope_boundaries_preserve_way_orientation(self) -> None:
        typ = TYP.read_text(encoding="utf-8")
        for code in ("0x10f17", "0x10d01", "0x10d02"):
            with self.subTest(code=code):
                match = re.search(rf"(?ms)^\[_line\]\nType={code}\n(.*?)^\[end\]", typ)
                self.assertIsNotNone(match)
                section = match.group(1)
                self.assertIn("UseOrientation=Y", section)
                self.assertNotIn("UseOrientation=N", section)


if __name__ == "__main__":
    unittest.main()

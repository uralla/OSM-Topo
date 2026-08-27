from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"

class CliffTypOrientationTests(unittest.TestCase):
    def test_cliff_preserves_way_orientation(self) -> None:
        typ = TYP.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^\[_line\]\nType=0x10f17\n(.*?)^\[end\]", typ)
        self.assertIsNotNone(match)
        section = match.group(1)
        self.assertIn("UseOrientation=Y", section)
        self.assertNotIn("UseOrientation=N", section)

if __name__ == "__main__":
    unittest.main()

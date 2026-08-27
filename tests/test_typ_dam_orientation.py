from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"
WATER_LINES = ROOT / "styles" / "uralla" / "inc" / "water_lines"
LINES = ROOT / "styles" / "uralla" / "lines"

class DamTypOrientationTests(unittest.TestCase):
    def test_dam_visual_is_directional_and_shared_with_weir(self) -> None:
        typ = TYP.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^\[_line\]\nType=0x12d01\n(.*?)^\[end\]", typ)
        self.assertIsNotNone(match)
        section = match.group(1)
        self.assertIn("UseOrientation=Y", section)
        self.assertIn('Xpm="32 7 2  1"', section)
        self.assertEqual(section.count('"!   !   !   !   !   !   !   !   "'), 4)
        self.assertEqual(section.count('"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"'), 2)

        water = WATER_LINES.read_text(encoding="utf-8")
        lines = LINES.read_text(encoding="utf-8")
        self.assertIn("waterway=weir [0x12d01 resolution 23 continue]", water)
        self.assertIn("waterway=dam [0x12d01 resolution 23]", lines)

if __name__ == "__main__":
    unittest.main()

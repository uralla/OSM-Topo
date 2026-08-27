from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"


class LandmarkTypLabelTests(unittest.TestCase):
    def test_2c04_has_hover_only_label(self) -> None:
        typ = TYP.read_text(encoding="utf-8")
        match = re.search(
            r"(?ms)^\[_point\]\nType=0x02c\nSubType=0x04\n(.*?)^\[end\]",
            typ,
        )
        self.assertIsNotNone(match)
        section = match.group(1)
        self.assertIn("ExtendedLabels=Y", section)
        self.assertIn("FontStyle=NoLabel (invisible)", section)
        self.assertNotIn("ExtendedLabels=N", section)


if __name__ == "__main__":
    unittest.main()

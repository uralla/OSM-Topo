from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"

class EmbankmentTypLabelTests(unittest.TestCase):
    def test_10d01_is_named_embankment_not_gully(self) -> None:
        typ = TYP.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^\[_line\]\nType=0x10d01\n(.*?)^\[end\]", typ)
        self.assertIsNotNone(match)
        section = match.group(1)
        self.assertIn("String1=0x19,насыпь", section)
        self.assertIn("String2=0x04,embankment", section)
        self.assertNotIn("String1=0x19,овраг", section)

if __name__ == "__main__":
    unittest.main()

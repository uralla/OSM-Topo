import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalityLabelTypTests(unittest.TestCase):
    def test_named_and_unnamed_locality_style_contract(self) -> None:
        style = (ROOT / "styles/uralla/inc/place_points").read_text(encoding="utf-8")
        self.assertIn(
            "place=locality & name=* & mkgmap:area2poi!=true { name '${name}' } [0x6408 resolution 24]",
            style,
        )
        self.assertIn(
            "place=locality & name!=* & mkgmap:area2poi!=true { set mkgmap:label:1=' ' } [0x6408 resolution 24]",
            style,
        )

    def test_6408_typ_allows_real_labels(self) -> None:
        typ = (ROOT / "styles/uralla.txt").read_text(encoding="utf-8")
        match = re.search(
            r"\[_point\]\s*\nType=0x064\s*\nSubType=0x08\s*\n(?P<body>.*?)\n\[end\]",
            typ,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "0x6408 point block not found")
        body = match.group("body")
        self.assertIn("FontStyle=NormalFont", body)
        self.assertNotIn("FontStyle=NoLabel", body)


if __name__ == "__main__":
    unittest.main()

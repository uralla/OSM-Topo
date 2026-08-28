from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WATER_POINTS = PROJECT_ROOT / "styles/uralla/inc/water_points"
TYP = PROJECT_ROOT / "styles/uralla.txt"


class HotSpringStyleTests(unittest.TestCase):
    def test_hot_spring_uses_historical_type_at_resolution_22(self) -> None:
        text = WATER_POINTS.read_text(encoding="utf-8")
        self.assertIn(
            "natural=hot_spring & mkgmap:area2poi!=true [0x13703 resolution 22]",
            text,
        )

    def test_hot_spring_typ_exists_with_expected_labels(self) -> None:
        text = TYP.read_text(encoding="utf-8")
        match = re.search(
            r"(?ms)^\[_point\]\nType=0x137\nSubType=0x03\n(.*?)^\[end\]",
            text,
        )
        self.assertIsNotNone(match)
        section = match.group(1)
        self.assertIn("String1=0x19,горячий источник", section)
        self.assertIn("String2=0x04,hot spring", section)
        self.assertIn("ExtendedLabels=Y", section)


if __name__ == "__main__":
    unittest.main()

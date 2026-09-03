from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WATER_POINTS = PROJECT_ROOT / "styles/uralla/inc/water_points"
TYP = PROJECT_ROOT / "styles/uralla.txt"


class HotSpringStyleTests(unittest.TestCase):
    def test_hot_spring_uses_device_safe_type_at_resolution_22(self) -> None:
        text = WATER_POINTS.read_text(encoding="utf-8")
        self.assertIn(
            "natural=hot_spring & mkgmap:area2poi!=true [0x6416 resolution 22]",
            text,
        )

    def test_hot_spring_typ_keeps_original_design_after_remap(self) -> None:
        text = TYP.read_text(encoding="utf-8")
        match = re.search(
            r"(?ms)^\[_point\]\nType=0x064\nSubType=0x16\n(.*?)^\[end\]",
            text,
        )
        self.assertIsNotNone(match)
        section = match.group(1)
        self.assertIn(
            ";GRMN_TYPE: Business - Services Extended/TAXI_STAND(NT)/Taxi stand/NT",
            section,
        )
        self.assertIn("String1=0x19,горячий источник", section)
        self.assertIn("String2=0x04,hot spring", section)
        self.assertIn("ExtendedLabels=N", section)
        self.assertNotIn("ExtendedLabels=Y", section)
        self.assertIn('DayXpm="12 12 3 1"   Colormode=16', section)
        self.assertIn('"!\tc #FF0000"', section)
        self.assertIn('"#\tc #FFFFFF"', section)
        self.assertIn('"  \tc none"', section)
        self.assertIn('"  ###!!###  "', section)
        self.assertIn('"   ####     "', section)


if __name__ == "__main__":
    unittest.main()

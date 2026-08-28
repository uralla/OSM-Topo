from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "styles" / "uralla" / "points"
TYP = ROOT / "styles" / "uralla.txt"


class RailwayPointsStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POINTS.read_text(encoding="utf-8")

    def test_station_overview_and_detailed_icons_do_not_overlap(self) -> None:
        self.assertIn(
            "railway=station & !(layer<0) [0x2f17 resolution 24 continue]",
            self.text,
        )
        self.assertIn(
            "railway=station & !(layer<0) [0x11601 resolution 21-23]",
            self.text,
        )
        self.assertNotIn(
            "railway=station & !(layer<0) [0x11601 resolution 21]",
            self.text,
        )

    def test_halt_overview_and_detailed_icons_do_not_overlap(self) -> None:
        detailed = "( public_transport=platform & rail=yes & mkgmap:area2poi!=true) | railway=halt [0x2f17 resolution 24 continue]"
        overview = "( public_transport=platform & rail=yes & mkgmap:area2poi!=true) | railway=halt [0x11601 resolution 19-23]"
        self.assertIn(detailed, self.text)
        self.assertIn(overview, self.text)
        self.assertNotIn(
            "( public_transport=platform & rail=yes & mkgmap:area2poi!=true) | railway=halt [0x11601 resolution 19]",
            self.text,
        )

    def test_milestone_keeps_details_but_hides_permanent_label(self) -> None:
        self.assertRegex(
            self.text,
            r"railway=milestone\s+\{name '\$\{distance\} \(\$\{ref\}\)' \| '\$\{distance\}'\} \[0x1341e resolution 24\]",
        )

        typ = TYP.read_text(encoding="utf-8")
        match = re.search(
            r"(?ms)^\[_point\]\nType=0x134\nSubType=0x1e\n.*?^\[end\]",
            typ,
        )
        self.assertIsNotNone(match)
        section = match.group(0)
        self.assertIn("ExtendedLabels=Y", section)
        self.assertIn("FontStyle=NoLabel (invisible)", section)

    def test_signal_and_buffer_stop_are_close_zoom_and_unlabelled(self) -> None:
        self.assertIn("railway=buffer_stop [0x1341d resolution 24]", self.text)
        self.assertIn("railway=signal [0x1341f resolution 24]", self.text)

        typ = TYP.read_text(encoding="utf-8")
        for subtype, designation in (("1d", "тупик"), ("1f", "семафор")):
            match = re.search(
                rf"(?ms)^\[_point\]\nType=0x134\nSubType=0x{subtype}\n.*?^\[end\]",
                typ,
            )
            self.assertIsNotNone(match)
            section = match.group(0)
            self.assertIn(f"String1=0x19,{designation}", section)
            self.assertIn("ExtendedLabels=Y", section)
            self.assertIn("FontStyle=NoLabel (invisible)", section)


if __name__ == "__main__":
    unittest.main()

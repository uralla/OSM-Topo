from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WATER_LINES = ROOT / "styles" / "uralla" / "inc" / "water_lines"


class RailwayBridgeOverlayTests(unittest.TestCase):
    def test_active_railway_bridges_share_bridge_overlay(self) -> None:
        text = WATER_LINES.read_text(encoding="utf-8")
        rule = (
            "railway=* & bridge=* & bridge!=no & bridge!=proposed & bridge!=abandoned & area!=yes & tunnel!=yes\n"
            "& railway!=proposed & railway!=abandoned & railway!=disused & proposed!=* & disused!=yes & abandoned!=yes\n"
            "& !(railway=light_rail & layer<0) [0x10f16 resolution 24 continue]"
        )
        self.assertIn(rule, text)
        self.assertLess(text.index(rule), text.index("railway=narrow_gauge & disused!=yes & abandoned!=yes"))

    def test_overlay_excludes_removed_and_hidden_railways(self) -> None:
        text = WATER_LINES.read_text(encoding="utf-8")
        for predicate in (
            "railway!=proposed",
            "railway!=abandoned",
            "railway!=disused",
            "proposed!=*",
            "disused!=yes",
            "abandoned!=yes",
            "tunnel!=yes",
            "!(railway=light_rail & layer<0)",
        ):
            self.assertIn(predicate, text)


if __name__ == "__main__":
    unittest.main()

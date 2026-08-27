from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WATER_LINES = ROOT / "styles" / "uralla" / "inc" / "water_lines"


class GroyneWaterStructureStyleTests(unittest.TestCase):
    def test_groyne_and_quay_share_existing_pier_breakwater_visual(self) -> None:
        text = WATER_LINES.read_text(encoding="utf-8")
        self.assertIn(
            "(man_made=pier | man_made=breakwater | man_made=groyne | man_made=quay) & is_closed()=true",
            text,
        )
        self.assertIn(
            "man_made=groyne & is_closed()=false & area!=yes { name '${name}' | 'буна'; set uralla:pier_rendered=yes } [0x10f07 resolution 24 continue]",
            text,
        )
        self.assertIn(
            "man_made=quay & is_closed()=false & area!=yes { name '${name}' | 'набережная'; set uralla:pier_rendered=yes } [0x10f07 resolution 24 continue]",
            text,
        )


if __name__ == "__main__":
    unittest.main()

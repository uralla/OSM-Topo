from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / "styles" / "uralla" / "inc" / "priority_points"
RELIEF = ROOT / "styles" / "uralla" / "inc" / "landuse_points"


class MountainPassStyleTests(unittest.TestCase):
    def test_generic_saddle_does_not_consume_mountain_pass(self) -> None:
        text = PRIORITY.read_text(encoding="utf-8")
        self.assertIn("natural=saddle & mountain_pass!=yes [0x11507 resolution 23]", text)
        self.assertNotIn("\nnatural=saddle [0x11507 resolution 23]", text)

    def test_detailed_mountain_pass_rule_keeps_rich_labels(self) -> None:
        text = RELIEF.read_text(encoding="utf-8")
        self.assertIn("mountain_pass=yes {name", text)
        self.assertIn("${rtsa_scale}", text)
        self.assertIn("${pass:category}", text)
        self.assertIn("[0x11507 resolution 23]", text)


if __name__ == "__main__":
    unittest.main()

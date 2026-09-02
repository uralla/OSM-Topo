from pathlib import Path
import unittest


class NordicPathPriorityTests(unittest.TestCase):
    def test_nordic_visual_requires_absent_highway(self) -> None:
        text = Path("styles/uralla/inc/water_lines").read_text(encoding="utf-8")
        self.assertIn(
            "piste:type=nordic & highway!=* & is_closed()=false & area!=yes [0x10101 resolution 22]",
            text,
        )
        self.assertNotIn("highway=path | highway=footway", text)

    def test_any_physical_highway_strips_piste_visual_override(self) -> None:
        text = Path("styles/uralla/lines").read_text(encoding="utf-8")
        self.assertIn("highway=* & piste:type=*\n{ delete piste:type; delete piste:grooming }", text)


if __name__ == "__main__":
    unittest.main()

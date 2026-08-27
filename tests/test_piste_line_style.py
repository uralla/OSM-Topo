from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / "styles" / "uralla" / "lines"


class PisteLineStyleTests(unittest.TestCase):
    def test_hard_downhill_difficulties_share_hardest_visual_type(self) -> None:
        lines = LINES.read_text(encoding="utf-8")
        rule = "(piste:type=downhill & piste:difficulty=advanced | piste:type=downhill & piste:difficulty=expert | piste:type=downhill & piste:difficulty=freeride | piste:type=downhill & piste:difficulty=extreme) & is_closed()=false & area!=yes [0x10104 resolution 22]"
        self.assertIn(rule, lines)
        for value in ("advanced", "expert", "freeride", "extreme"):
            self.assertIn(f"piste:difficulty={value}", rule)


if __name__ == "__main__":
    unittest.main()

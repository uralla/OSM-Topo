from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_piste_line_style.py')

lines = LINES.read_text(encoding='utf-8')
old = "piste:type=downhill & piste:difficulty=advanced & is_closed()=false & area!=yes [0x10104 resolution 22]\n"
new = "(piste:type=downhill & piste:difficulty=advanced | piste:type=downhill & piste:difficulty=expert | piste:type=downhill & piste:difficulty=freeride | piste:type=downhill & piste:difficulty=extreme) & is_closed()=false & area!=yes [0x10104 resolution 22]\n"
if lines.count(old) != 1:
    raise SystemExit(f'expected one advanced piste rule, got {lines.count(old)}')
LINES.write_text(lines.replace(old, new, 1), encoding='utf-8', newline='\n')

TEST.write_text('''from pathlib import Path\nimport unittest\n\n\nROOT = Path(__file__).resolve().parents[1]\nLINES = ROOT / "styles" / "uralla" / "lines"\n\n\nclass PisteLineStyleTests(unittest.TestCase):\n    def test_hard_downhill_difficulties_share_hardest_visual_type(self) -> None:\n        lines = LINES.read_text(encoding="utf-8")\n        rule = "(piste:type=downhill & piste:difficulty=advanced | piste:type=downhill & piste:difficulty=expert | piste:type=downhill & piste:difficulty=freeride | piste:type=downhill & piste:difficulty=extreme) & is_closed()=false & area!=yes [0x10104 resolution 22]"\n        self.assertIn(rule, lines)\n        for value in ("advanced", "expert", "freeride", "extreme"):\n            self.assertIn(f"piste:difficulty={value}", rule)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8', newline='\n')

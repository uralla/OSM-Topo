from pathlib import Path
import re

TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_typ_cliff_orientation.py')

typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(r'(?ms)(^\[_line\]\nType=0x10f17\n;GRMN_TYPE:.*?\n)UseOrientation=N\n')
matches = list(pattern.finditer(typ))
if len(matches) != 1:
    raise SystemExit(f'expected one 0x10f17 section with UseOrientation=N, got {len(matches)}')
typ = pattern.sub(r'\1UseOrientation=Y\n', typ, count=1)
TYP.write_text(typ, encoding='utf-8', newline='\n')

TEST.write_text('''from pathlib import Path\nimport re\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nTYP = ROOT / "styles" / "uralla.txt"\n\nclass CliffTypOrientationTests(unittest.TestCase):\n    def test_cliff_preserves_way_orientation(self) -> None:\n        typ = TYP.read_text(encoding="utf-8")\n        match = re.search(r"(?ms)^\\[_line\\]\\nType=0x10f17\\n(.*?)^\\[end\\]", typ)\n        self.assertIsNotNone(match)\n        section = match.group(1)\n        self.assertIn("UseOrientation=Y", section)\n        self.assertNotIn("UseOrientation=N", section)\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8', newline='\n')

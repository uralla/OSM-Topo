from pathlib import Path
import re

TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_typ_landmark_label.py')

typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(r'(?ms)(^\[_point\]\nType=0x02c\nSubType=0x04\n.*?^String2=0x04,landmark\n)ExtendedLabels=N\n')
matches = list(pattern.finditer(typ))
if len(matches) != 1:
    raise SystemExit(f'expected one 0x02c/0x04 point section, got {len(matches)}')
typ = pattern.sub(r'\1ExtendedLabels=Y\nFontStyle=NoLabel (invisible)\n', typ, count=1)
TYP.write_text(typ, encoding='utf-8', newline='\n')

TEST.write_text('''from pathlib import Path\nimport re\nimport unittest\n\n\nROOT = Path(__file__).resolve().parents[1]\nTYP = ROOT / "styles" / "uralla.txt"\n\n\nclass LandmarkTypLabelTests(unittest.TestCase):\n    def test_2c04_has_hover_only_label(self) -> None:\n        typ = TYP.read_text(encoding="utf-8")\n        match = re.search(\n            r"(?ms)^\\[_point\\]\\nType=0x02c\\nSubType=0x04\\n(.*?)^\\[end\\]",\n            typ,\n        )\n        self.assertIsNotNone(match)\n        section = match.group(1)\n        self.assertIn("ExtendedLabels=Y", section)\n        self.assertIn("FontStyle=NoLabel (invisible)", section)\n        self.assertNotIn("ExtendedLabels=N", section)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8', newline='\n')

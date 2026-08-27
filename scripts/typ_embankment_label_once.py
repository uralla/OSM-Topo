from pathlib import Path
import re

TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_typ_embankment_label.py')

typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(r'(?ms)(^\[_line\]\nType=0x10d01\n.*?^;12345678901234567890123456789012\n)String1=0x19,овраг\nString2=0x04,gully\n')
matches = list(pattern.finditer(typ))
if len(matches) != 1:
    raise SystemExit(f'expected one 0x10d01 section, got {len(matches)}')
typ = pattern.sub(r'\1String1=0x19,насыпь\nString2=0x04,embankment\n', typ, count=1)
TYP.write_text(typ, encoding='utf-8', newline='\n')

TEST.write_text('''from pathlib import Path\nimport re\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nTYP = ROOT / "styles" / "uralla.txt"\n\nclass EmbankmentTypLabelTests(unittest.TestCase):\n    def test_10d01_is_named_embankment_not_gully(self) -> None:\n        typ = TYP.read_text(encoding="utf-8")\n        match = re.search(r"(?ms)^\\[_line\\]\\nType=0x10d01\\n(.*?)^\\[end\\]", typ)\n        self.assertIsNotNone(match)\n        section = match.group(1)\n        self.assertIn("String1=0x19,насыпь", section)\n        self.assertIn("String2=0x04,embankment", section)\n        self.assertNotIn("String1=0x19,овраг", section)\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8', newline='\n')

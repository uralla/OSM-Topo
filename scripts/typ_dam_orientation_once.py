from pathlib import Path
import re

TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_typ_dam_orientation.py')

typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(
    r'(?ms)(^\[_line\]\nType=0x12d01\n;GRMN_TYPE:.*?\nUseOrientation=Y\n)'
    r'Xpm="32 12 2  1"\n'
    r'"! c #101010"\n'
    r'"  c none"\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r'"                                "\n'
    r'"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"\n'
    r'"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"\n'
    r'"                                "\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r'"!   !   !   !   !   !   !   !   "\n'
    r';12345678901234567890123456789012\n'
)
matches = list(pattern.finditer(typ))
if len(matches) != 1:
    raise SystemExit(f'expected one symmetric 0x12d01 section, got {len(matches)}')
replacement = (
    r'\1'
    'Xpm="32 7 2  1"\n'
    '"! c #101010"\n'
    '"  c none"\n'
    '"!   !   !   !   !   !   !   !   "\n'
    '"!   !   !   !   !   !   !   !   "\n'
    '"!   !   !   !   !   !   !   !   "\n'
    '"!   !   !   !   !   !   !   !   "\n'
    '"                                "\n'
    '"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"\n'
    '"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"\n'
    ';12345678901234567890123456789012\n'
)
typ = pattern.sub(replacement, typ, count=1)
TYP.write_text(typ, encoding='utf-8', newline='\n')

TEST.write_text('''from pathlib import Path\nimport re\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nTYP = ROOT / "styles" / "uralla.txt"\nWATER_LINES = ROOT / "styles" / "uralla" / "inc" / "water_lines"\nLINES = ROOT / "styles" / "uralla" / "lines"\n\nclass DamTypOrientationTests(unittest.TestCase):\n    def test_dam_visual_is_directional_and_shared_with_weir(self) -> None:\n        typ = TYP.read_text(encoding="utf-8")\n        match = re.search(r"(?ms)^\\[_line\\]\\nType=0x12d01\\n(.*?)^\\[end\\]", typ)\n        self.assertIsNotNone(match)\n        section = match.group(1)\n        self.assertIn("UseOrientation=Y", section)\n        self.assertIn('Xpm="32 7 2  1"', section)\n        self.assertEqual(section.count('"!   !   !   !   !   !   !   !   "'), 4)\n        self.assertEqual(section.count('"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"'), 2)\n\n        water = WATER_LINES.read_text(encoding="utf-8")\n        lines = LINES.read_text(encoding="utf-8")\n        self.assertIn("waterway=weir [0x12d01 resolution 23 continue]", water)\n        self.assertIn("waterway=dam [0x12d01 resolution 23]", lines)\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8', newline='\n')

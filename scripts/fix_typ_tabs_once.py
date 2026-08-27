from pathlib import Path

TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_typ_literal_tabs.py')

text = TYP.read_text(encoding='utf-8')
needle = r'\tc '
count = text.count(needle)
if count != 7:
    raise SystemExit(f'expected 7 literal \\t color separators, got {count}')
text = text.replace(needle, '\tc ')
TYP.write_text(text, encoding='utf-8', newline='\n')

TEST.write_text("""from pathlib import Path\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nTYP = ROOT / 'styles' / 'uralla.txt'\n\nclass TypLiteralTabTests(unittest.TestCase):\n    def test_typ_contains_no_literal_backslash_t_color_separators(self) -> None:\n        text = TYP.read_text(encoding='utf-8')\n        self.assertNotIn(r'\\tc ', text)\n\nif __name__ == '__main__':\n    unittest.main()\n""", encoding='utf-8', newline='\n')

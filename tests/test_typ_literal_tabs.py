from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / 'styles' / 'uralla.txt'

class TypLiteralTabTests(unittest.TestCase):
    def test_typ_contains_no_literal_backslash_t_color_separators(self) -> None:
        text = TYP.read_text(encoding='utf-8')
        self.assertNotIn(r'\tc ', text)

if __name__ == '__main__':
    unittest.main()

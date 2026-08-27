from pathlib import Path

POINTS = Path('styles/uralla/points')
TEST = Path('tests/test_hut_point_style.py')

points = POINTS.read_text(encoding='utf-8')
needle = "tourism=camp_site {name '${name}' | 'кемпинг'} [0x2b03 resolution 24] #\ntourism=chalet [0x2b02 resolution 21]\ntourism=information {name '${name}' | 'информация'} [0x4c00 resolution 24]"
replacement = "tourism=camp_site {name '${name}' | 'кемпинг'} [0x2b03 resolution 24] #\n# Mountain huts: staffed alpine huts use lodging visual; unstaffed wilderness huts use shelter visual.\ntourism=alpine_hut [0x2b02 resolution 21]\ntourism=chalet [0x2b02 resolution 21]\ntourism=wilderness_hut [0x2b05 resolution 23]\ntourism=information {name '${name}' | 'информация'} [0x4c00 resolution 24]"
if points.count(needle) != 1:
    raise SystemExit(f'expected one tourism hut insertion point, got {points.count(needle)}')
points = points.replace(needle, replacement, 1)
POINTS.write_text(points, encoding='utf-8', newline='\n')

TEST.write_text("""from pathlib import Path\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nPOINTS = ROOT / 'styles' / 'uralla' / 'points'\n\nclass HutPointStyleTests(unittest.TestCase):\n    def test_alpine_and_wilderness_huts_are_rendered(self) -> None:\n        points = POINTS.read_text(encoding='utf-8')\n        self.assertIn(\"tourism=alpine_hut [0x2b02 resolution 21]\", points)\n        self.assertIn(\"tourism=wilderness_hut [0x2b05 resolution 23]\", points)\n        self.assertIn(\"amenity=shelter | tourism=lean_to [0x2b05 resolution 24]\", points)\n\nif __name__ == '__main__':\n    unittest.main()\n""", encoding='utf-8', newline='\n')

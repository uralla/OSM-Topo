from pathlib import Path

POINTS = Path('styles/uralla/points')
TEST = Path('tests/test_information_point_style.py')

points = POINTS.read_text(encoding='utf-8')
needle = "tourism=wilderness_hut [0x2b05 resolution 23]\ntourism=information {name '${name}' | 'информация'} [0x4c00 resolution 24]"
replacement = "tourism=wilderness_hut [0x2b05 resolution 23]\n# Route guideposts are strong navigation anchors; simple route markers stay close-zoom only.\ntourism=information & information=guidepost {name '${name}' | '${ref}' | 'указатель'} [0x4c00 resolution 23]\ntourism=information & information=route_marker {name '${name}' | '${ref}' | 'маркер'} [0x4c00 resolution 24]\ntourism=information {name '${name}' | 'информация'} [0x4c00 resolution 24]"
if points.count(needle) != 1:
    raise SystemExit(f'expected one information insertion point, got {points.count(needle)}')
points = points.replace(needle, replacement, 1)
POINTS.write_text(points, encoding='utf-8', newline='\n')

TEST.write_text("""from pathlib import Path\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nPOINTS = ROOT / 'styles' / 'uralla' / 'points'\n\nclass InformationPointStyleTests(unittest.TestCase):\n    def test_guideposts_are_prioritized_over_generic_information(self) -> None:\n        points = POINTS.read_text(encoding='utf-8')\n        guidepost = \"tourism=information & information=guidepost {name '${name}' | '${ref}' | 'указатель'} [0x4c00 resolution 23]\"\n        route_marker = \"tourism=information & information=route_marker {name '${name}' | '${ref}' | 'маркер'} [0x4c00 resolution 24]\"\n        generic = \"tourism=information {name '${name}' | 'информация'} [0x4c00 resolution 24]\"\n        self.assertIn(guidepost, points)\n        self.assertIn(route_marker, points)\n        self.assertIn(generic, points)\n        self.assertLess(points.index(guidepost), points.index(generic))\n        self.assertLess(points.index(route_marker), points.index(generic))\n\nif __name__ == '__main__':\n    unittest.main()\n""", encoding='utf-8', newline='\n')

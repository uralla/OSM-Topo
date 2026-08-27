from pathlib import Path

POINTS = Path('styles/uralla/points')
TEST = Path('tests/test_emergency_phone_style.py')

points = POINTS.read_text(encoding='utf-8')
needle = "amenity=taxi [0x2f11 resolution 24]\namenity=telephone [0x2f12 resolution 24]"
replacement = "amenity=taxi [0x2f11 resolution 24]\n# Emergency-only phones are more important on a topo map than ordinary public telephones.\nemergency=phone [0x2f12 resolution 23]\namenity=telephone [0x2f12 resolution 24]"
if points.count(needle) != 1:
    raise SystemExit(f'expected one telephone insertion point, got {points.count(needle)}')
points = points.replace(needle, replacement, 1)
POINTS.write_text(points, encoding='utf-8', newline='\n')

TEST.write_text("""from pathlib import Path\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nPOINTS = ROOT / 'styles' / 'uralla' / 'points'\n\nclass EmergencyPhoneStyleTests(unittest.TestCase):\n    def test_emergency_phone_is_visible_before_ordinary_telephone(self) -> None:\n        points = POINTS.read_text(encoding='utf-8')\n        self.assertIn(\"emergency=phone [0x2f12 resolution 23]\", points)\n        self.assertIn(\"amenity=telephone [0x2f12 resolution 24]\", points)\n        self.assertLess(points.index(\"emergency=phone [0x2f12 resolution 23]\"), points.index(\"amenity=telephone [0x2f12 resolution 24]\"))\n\nif __name__ == '__main__':\n    unittest.main()\n""", encoding='utf-8', newline='\n')

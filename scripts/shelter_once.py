from pathlib import Path

POINTS = Path('styles/uralla/points')
TEST = Path('tests/test_shelter_point_style.py')

points = POINTS.read_text(encoding='utf-8')
old_comment = "# amenity=shelter is ambiguous; when possible, consider using other tags:\n#  tourism=lean_to or tourism=picnic_site\n#  shelter=yes on highway=bus_stop or highway=tram_stop or railway=halt"
new_comment = "# amenity=shelter is the standard OSM tag for small weather shelters;\n# shelter_type=* refines lean-to/basic hut/picnic/weather shelter.\n# Keep legacy tourism=lean_to as a compatibility fallback."
if points.count(old_comment) != 1:
    raise SystemExit(f'expected one stale shelter comment, got {points.count(old_comment)}')
points = points.replace(old_comment, new_comment, 1)
old_rule = "# tourism=lean_to replaces some uses of amenity=shelter\ntourism=lean_to [0x2b05 resolution 24]"
new_rule = "# Standard shelter plus legacy lean_to fallback share the existing shelter icon.\namenity=shelter | tourism=lean_to [0x2b05 resolution 24]"
if points.count(old_rule) != 1:
    raise SystemExit(f'expected one legacy lean_to rule, got {points.count(old_rule)}')
points = points.replace(old_rule, new_rule, 1)
POINTS.write_text(points, encoding='utf-8', newline='\n')

TEST.write_text("""from pathlib import Path\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\nPOINTS = ROOT / 'styles' / 'uralla' / 'points'\n\nclass ShelterPointStyleTests(unittest.TestCase):\n    def test_standard_osm_shelter_uses_existing_shelter_icon(self) -> None:\n        points = POINTS.read_text(encoding='utf-8')\n        self.assertIn(\"amenity=shelter | tourism=lean_to [0x2b05 resolution 24]\", points)\n        self.assertNotIn(\"tourism=lean_to [0x2b05 resolution 24]\", points.replace(\"amenity=shelter | tourism=lean_to [0x2b05 resolution 24]\", \"\"))\n        self.assertNotIn(\"tourism=lean_to replaces some uses of amenity=shelter\", points)\n\nif __name__ == '__main__':\n    unittest.main()\n""", encoding='utf-8', newline='\n')

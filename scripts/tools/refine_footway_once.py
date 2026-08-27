from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')
CI = Path('.github/workflows/ci.yml')
SELF = Path('scripts/tools/refine_footway_once.py')

lines = LINES.read_text(encoding='utf-8')

old = "footway=sidewalk & highway=steps | highway=steps [0x12d1f resolution 24 continue]\nhighway=steps [0x16 road_class=0 road_speed=0 resolution 24]"
new = "highway=steps [0x12d1f resolution 24 continue]\nhighway=steps [0x16 road_class=0 road_speed=0 resolution 24]"
if old not in lines:
    raise SystemExit('steps block not found')
lines = lines.replace(old, new, 1)

old = "mkgmap:trail_name=* & highway=footway & length()>100 [0x07 resolution 21-22 continue]\nmkgmap:trail_name=* & highway=footway & length()>100 [0x0e road_class=0 road_speed=1 resolution 23-24]"
new = "# Urban sidewalk/crossing footways stay in the pedestrian visual class.\nmkgmap:trail_name=* & highway=footway & (footway=sidewalk | footway=crossing) & length()>100 [0x07 resolution 21-22 continue]\nmkgmap:trail_name=* & highway=footway & (footway=sidewalk | footway=crossing) & length()>100 [0x0e road_class=0 road_speed=0 resolution 23-24]\n# Other designated footways are topo trails, not pedestrian streets.\nmkgmap:trail_name=* & highway=footway & footway!=sidewalk & footway!=crossing & length()>100 [0x0b resolution 22-22 continue]\nmkgmap:trail_name=* & highway=footway & footway!=sidewalk & footway!=crossing & length()>100 [0x16 road_class=0 road_speed=0 resolution 23-24]"
if old not in lines:
    raise SystemExit('marked footway block not found')
lines = lines.replace(old, new, 1)

old = "highway=footway & length()>100 [0x07 resolution 22-23 continue]\nhighway=footway [0x0e road_class=0 road_speed=1 resolution 24]"
new = "# Sidewalks/crossings use the pedestrian visual class; other footways use the trail class.\nhighway=footway & (footway=sidewalk | footway=crossing) & length()>100 [0x07 resolution 22-23 continue]\nhighway=footway & (footway=sidewalk | footway=crossing) [0x0e road_class=0 road_speed=0 resolution 24]\nhighway=footway & footway!=sidewalk & footway!=crossing & length()>100 [0x0b resolution 23-23 continue]\nhighway=footway & footway!=sidewalk & footway!=crossing [0x16 road_class=0 road_speed=0 resolution 24]"
if old not in lines:
    raise SystemExit('base footway block not found')
lines = lines.replace(old, new, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor = "    def test_footway_is_not_duplicated_by_bicycle_path_rule(self) -> None:\n"
if anchor not in test:
    raise SystemExit('test anchor missing')
block = '''    def test_footway_sidewalk_and_trail_semantics_are_separate(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        self.assertIn(\n            "highway=footway & (footway=sidewalk | footway=crossing) & length()>100 [0x07 resolution 22-23 continue]",\n            lines,\n        )\n        self.assertIn(\n            "highway=footway & (footway=sidewalk | footway=crossing) [0x0e road_class=0 road_speed=0 resolution 24]",\n            lines,\n        )\n        self.assertIn(\n            "highway=footway & footway!=sidewalk & footway!=crossing & length()>100 [0x0b resolution 23-23 continue]",\n            lines,\n        )\n        self.assertIn(\n            "highway=footway & footway!=sidewalk & footway!=crossing [0x16 road_class=0 road_speed=0 resolution 24]",\n            lines,\n        )\n        self.assertNotIn("footway=sidewalk & highway=steps", lines)\n        self.assertIn("highway=steps [0x12d1f resolution 24 continue]", lines)\n\n'''
test = test.replace(anchor, block + anchor, 1)
# Update the older footway expectation to the new trail far rule.
test = test.replace(
    '"highway=footway & length()>100 [0x07 resolution 22-23 continue]",',
    '"highway=footway & footway!=sidewalk & footway!=crossing & length()>100 [0x0b resolution 23-23 continue]",',
)
TEST.write_text(test, encoding='utf-8', newline='\n')

# Restore permanent CI exactly and remove this helper before committing.
CI.write_text("""name: CI\n\non:\n  push:\n    branches: [main]\n  pull_request:\n\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v4\n\n      - name: Set up Python\n        uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n          cache: pip\n\n      - name: Install project\n        run: python -m pip install -e .\n\n      - name: Run unit tests\n        run: python -m unittest discover -s tests -v\n\n      - name: Audit style against TYP\n        run: python scripts/tools/style-typ-audit.py\n""", encoding='utf-8', newline='\n')
SELF.unlink()

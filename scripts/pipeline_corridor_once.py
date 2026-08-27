from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
old_comment = "# Pipelines have their own farther LOD rule. Keep the broad cable/pipe fallback\n# from consuming man_made=pipeline before it can reach that rule."
new_comment = "# Pipelines are mapped as infrastructure corridors, not only as visible surface pipes.\n# Keep them at close topo zooms regardless of tunnel/location, and prevent the broad fallback\n# from consuming man_made=pipeline before this dedicated rule."
if lines.count(old_comment) != 1:
    raise SystemExit(f'expected one pipeline comment block, got {lines.count(old_comment)}')
lines = lines.replace(old_comment, new_comment, 1)
old_rule = "man_made=pipeline & tunnel!=yes & location!=underground {name '${name}' | '${operator}'} [0x28 resolution 22]"
new_rule = "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 23]"
if lines.count(old_rule) != 1:
    raise SystemExit(f'expected one filtered pipeline rule, got {lines.count(old_rule)}')
lines = lines.replace(old_rule, new_rule, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
old_test = '''    def test_pipeline_reaches_its_dedicated_farther_lod_rule(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        self.assertIn("man_made!=pipeline & man_made ~ '.*pipe.*'", lines)\n        self.assertIn(\n            "man_made=pipeline & tunnel!=yes & location!=underground {name '${name}' | '${operator}'} [0x28 resolution 22]",\n            lines,\n        )\n        self.assertNotIn(\n            "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 22]",\n            lines,\n        )\n'''
new_test = '''    def test_pipeline_is_a_close_zoom_infrastructure_corridor(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        self.assertIn("man_made!=pipeline & man_made ~ '.*pipe.*'", lines)\n        self.assertIn(\n            "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 23]",\n            lines,\n        )\n        self.assertNotIn("man_made=pipeline & tunnel!=yes", lines)\n        self.assertNotIn("man_made=pipeline & location!=underground", lines)\n        self.assertNotIn(\n            "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 22]",\n            lines,\n        )\n'''
if test.count(old_test) != 1:
    raise SystemExit(f'expected one pipeline regression block, got {test.count(old_test)}')
test = test.replace(old_test, new_test, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

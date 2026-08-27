from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
old = "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 22]"
new = "man_made=pipeline & tunnel!=yes & location!=underground {name '${name}' | '${operator}'} [0x28 resolution 22]"
if lines.count(old) != 1:
    raise SystemExit(f'expected exactly one pipeline rule, got {lines.count(old)}')
lines = lines.replace(old, new, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
old_test = '''        self.assertIn(\n            "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 22]",\n            lines,\n        )'''
new_test = '''        self.assertIn(\n            "man_made=pipeline & tunnel!=yes & location!=underground {name '${name}' | '${operator}'} [0x28 resolution 22]",\n            lines,\n        )\n        self.assertNotIn(\n            "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 22]",\n            lines,\n        )'''
if test.count(old_test) != 1:
    raise SystemExit(f'expected exactly one pipeline regression block, got {test.count(old_test)}')
test = test.replace(old_test, new_test, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

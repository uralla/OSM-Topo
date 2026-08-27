from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
old_road = "highway=* & (bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path\n\t& area!=yes [0x10f16 resolution 24 continue]"
new_road = "highway=* & bridge=* & bridge!=no & bridge!=proposed & bridge!=abandoned & highway!=pedestrian & highway!=footway & highway!=path\n\t& area!=yes [0x10f16 resolution 24 continue]"
if lines.count(old_road) != 1:
    raise SystemExit(f'expected one road bridge rule, got {lines.count(old_road)}')
lines = lines.replace(old_road, new_road, 1)
old_foot = "(bridge=yes | bridge=true) & (highway=pedestrian | highway=footway | highway=path)\n\t& area!=yes [0x10f18 resolution 24 continue]"
new_foot = "bridge=* & bridge!=no & bridge!=proposed & bridge!=abandoned & (highway=pedestrian | highway=footway | highway=path)\n\t& area!=yes [0x10f18 resolution 24 continue]"
if lines.count(old_foot) != 1:
    raise SystemExit(f'expected one foot bridge rule, got {lines.count(old_foot)}')
lines = lines.replace(old_foot, new_foot, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
old = "        bridge = \"highway=* & (bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path\""
new = "        bridge = \"highway=* & bridge=* & bridge!=no & bridge!=proposed & bridge!=abandoned & highway!=pedestrian & highway!=footway & highway!=path\""
if test.count(old) != 1:
    raise SystemExit(f'expected one bridge regression predicate, got {test.count(old)}')
test = test.replace(old, new, 1)
old_not = "        self.assertNotIn(\"\\n(bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path\", lines)"
new_not = "        self.assertNotIn(\"\\nbridge=* & bridge!=no & bridge!=proposed & bridge!=abandoned & highway!=pedestrian & highway!=footway & highway!=path\", lines)"
if test.count(old_not) != 1:
    raise SystemExit(f'expected one bridge negative regression, got {test.count(old_not)}')
test = test.replace(old_not, new_not, 1)
insert_after = "        self.assertLess(lines.index(planned), lines.index(tunnel))\n"
extra = "        self.assertIn(\"bridge=* & bridge!=no & bridge!=proposed & bridge!=abandoned & (highway=pedestrian | highway=footway | highway=path)\", lines)\n"
if extra not in test:
    if test.count(insert_after) != 1:
        raise SystemExit('bridge regression insertion point not found')
    test = test.replace(insert_after, insert_after + extra, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

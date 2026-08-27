from pathlib import Path

POINTS = Path('styles/uralla/points')
TEST = Path('tests/test_information_point_style.py')

points = POINTS.read_text(encoding='utf-8')
old = "tourism=information & information=route_marker {name '${name}' | '${ref}' | 'маркер'} [0x4c00 resolution 24]"
new = "tourism=information & (information=route_marker | information=trail_blaze) {name '${name}' | '${ref}' | 'маркер'} [0x4c00 resolution 24]"
if points.count(old) != 1:
    raise SystemExit(f'expected one route marker rule, got {points.count(old)}')
points = points.replace(old, new, 1)
POINTS.write_text(points, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
old_test = "route_marker = \"tourism=information & information=route_marker {name '${name}' | '${ref}' | 'маркер'} [0x4c00 resolution 24]\""
new_test = "route_marker = \"tourism=information & (information=route_marker | information=trail_blaze) {name '${name}' | '${ref}' | 'маркер'} [0x4c00 resolution 24]\""
if test.count(old_test) != 1:
    raise SystemExit(f'expected one route marker regression line, got {test.count(old_test)}')
test = test.replace(old_test, new_test, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

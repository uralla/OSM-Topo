from pathlib import Path
import re

TYP = Path('styles/uralla.txt')
LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

# --- TYP: move the one remaining custom bad-track-near design onto routable MPC 0x13 ---
typ = TYP.read_text(encoding='utf-8')
if re.search(r'\[_line\]\nType=0x13\n', typ, flags=re.I):
    raise SystemExit('line Type=0x13 already exists in TYP; refusing to overwrite')

m = re.search(r'\n?\[_line\]\nType=0x13504\n.*?\n\[end\]\n?', typ, flags=re.S | re.I)
if not m:
    raise SystemExit('missing Type=0x13504 role block')
block = m.group(0).strip('\n')
block = re.sub(r'(?m)^Type=0x13504$', 'Type=0x13', block)
block = re.sub(
    r'(?m)^;URALLA_ROLE:.*$',
    ';URALLA_ROLE: forest-road-bad-near\n;GRMN_TYPE: Customizable Line Types/CUSTOMIZABLE_ROUTE_LINE_7/Routable customizable line/Non NT, NT',
    block,
    count=1,
)
typ = typ[:m.start()] + '\n' + typ[m.end():]

m12 = re.search(r'\[_line\]\nType=0x12\n.*?\n\[end\]', typ, flags=re.S | re.I)
if not m12:
    raise SystemExit('missing Type=0x12 block')
typ = typ[:m12.end()] + '\n\n\n' + block + typ[m12.end():]
TYP.write_text(typ, encoding='utf-8', newline='\n')

# --- style: bind the semantic classes to the canonical routable MPC types ---
lines = LINES.read_text(encoding='utf-8')
repls = {
    "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x2e resolution 22-22 continue]":
        "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x16 resolution 22-22 continue]",
    "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x0a resolution 21-21 continue]":
        "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x13 resolution 21-21 continue]",
    "bicycle!=yes & highway=path [0x2e road_class=0 road_speed=0 resolution 24]":
        "bicycle!=yes & highway=path [0x16 road_class=0 road_speed=0 resolution 24]",
    "highway=track [0x0a road_class=0 road_speed=1 resolution 24]":
        "highway=track & tracktype=grade1 [0x0a road_class=0 road_speed=1 resolution 24]\nhighway=track & tracktype!=grade1 [0x13 road_class=0 road_speed=1 resolution 24]",
}
for old, new in repls.items():
    if old not in lines:
        raise SystemExit(f'missing expected style rule: {old}')
    lines = lines.replace(old, new, 1)

ped_route = "mkgmap:trail_name=* & highway=pedestrian & area!=yes & length()>100 [0x0e resolution 21-21 continue]"
anchor = "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x0e resolution 21-21 continue]"
if ped_route not in lines:
    if anchor not in lines:
        raise SystemExit('missing marked cycleway anchor')
    lines = lines.replace(anchor, ped_route + '\n' + anchor, 1)

LINES.write_text(lines, encoding='utf-8', newline='\n')

# --- regression tests ---
test = TEST.read_text(encoding='utf-8')
test = test.replace(
    "lines.index('highway=track [0x0a road_class=0 road_speed=1 resolution 24]')",
    "lines.index('highway=track & tracktype!=grade1 [0x13 road_class=0 road_speed=1 resolution 24]')",
)
test = test.replace(
    '"mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x2e resolution 22-22 continue]",',
    '"mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x16 resolution 22-22 continue]",',
)
test = test.replace(
    '"mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x0a resolution 21-21 continue]",',
    '"mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x13 resolution 21-21 continue]",',
)
needle = '"mkgmap:trail_name=* & highway=cycleway & length()>100 [0x0e resolution 21-21 continue]",'
if 'highway=pedestrian & area!=yes & length()>100 [0x0e resolution 21-21 continue]' not in test:
    test = test.replace(
        needle,
        '"mkgmap:trail_name=* & highway=pedestrian & area!=yes & length()>100 [0x0e resolution 21-21 continue]",\n            ' + needle,
        1,
    )

insert_before = "    def test_footway_is_not_duplicated_by_bicycle_path_rule(self) -> None:\n"
new_test = '''    def test_canonical_road_and_trail_near_types_are_routable(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        self.assertIn("highway=track & tracktype=grade1 [0x0a road_class=0 road_speed=1 resolution 24]", lines)\n        self.assertIn("highway=track & tracktype!=grade1 [0x13 road_class=0 road_speed=1 resolution 24]", lines)\n        self.assertIn("bicycle=yes & highway=path [0x16 road_class=0 road_speed=1 resolution 24]", lines)\n        self.assertIn("bicycle!=yes & highway=path [0x16 road_class=0 road_speed=0 resolution 24]", lines)\n        self.assertNotIn("0x13504", lines)\n        self.assertNotIn("bicycle!=yes & highway=path [0x2e", lines)\n\n'''
if 'def test_canonical_road_and_trail_near_types_are_routable' not in test:
    if insert_before not in test:
        raise SystemExit('cannot locate test insertion point')
    test = test.replace(insert_before, new_test + insert_before, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

print('migrated road/trail style to canonical routable MPC types; 0x13504 -> 0x13')

from pathlib import Path
import re

POINTS = Path('styles/uralla/points')
TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_topo_marker_points.py')

points = POINTS.read_text(encoding='utf-8')

# Remove POIs explicitly unwanted on the topo map.
lines = points.splitlines()
new_lines = []
removed_nursing = 0
removed_car_dealer = 0
for line in lines:
    stripped = line.strip()
    if re.match(r'^amenity=nursing_home(?:\s|$)', stripped):
        removed_nursing += 1
        continue
    if re.match(r'^shop=car(?:\s|$)', stripped):
        removed_car_dealer += 1
        continue
    new_lines.append(line)

if removed_nursing != 1:
    raise SystemExit(f'expected one amenity=nursing_home rule, removed {removed_nursing}')
if removed_car_dealer != 1:
    raise SystemExit(f'expected one shop=car rule, removed {removed_car_dealer}')

points = '\n'.join(new_lines) + '\n'

anchor = "historic=boundary_stone [0x11500 resolution 24]\n"
insert = (
    "historic=boundary_stone [0x11500 resolution 24]\n"
    "# Small topo navigation markers. Labels stay in POI data but are hidden by TYP.\n"
    "man_made=cairn {name '${name}' | 'тура'} [0x11506 resolution 24]\n"
    "man_made=survey_point {name '${name}' | '${ref}' | 'геодезический пункт'} [0x11507 resolution 23]\n"
)
if points.count(anchor) != 1:
    raise SystemExit(f'expected one boundary stone insertion point, got {points.count(anchor)}')
points = points.replace(anchor, insert, 1)
POINTS.write_text(points, encoding='utf-8', newline='\n')

typ = TYP.read_text(encoding='utf-8')
if 'Type=0x115\nSubType=0x06' in typ or 'Type=0x115\nSubType=0x07' in typ:
    raise SystemExit('0x11506 or 0x11507 already exists in TYP')

typ_add = r'''

;===================== TOPO MARKERS =====================

[_point]
Type=0x115
SubType=0x06
; CUSTOM: cairn / stone navigation marker
String1=0x19,тура
String2=0x04,cairn
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
DayXpm="13 13 4 1"   Colormode=16
"!\tc #202020"
"#\tc #6F6F6F"
"%\tc #B5B5B5"
"  \tc none"
"             "
"      !!     "
"     !%%!    "
"    !%%%%!   "
"     !!!!    "
"    !####!   "
"   !######!  "
"    !!!!!!   "
"   !%%%%%%!  "
"  !%%%%%%%%! "
" !!!!!!!!!!! "
"             "
"             "
;1234567890123
[end]

[_point]
Type=0x115
SubType=0x07
; CUSTOM: survey / triangulation point
String1=0x19,геодезический пункт
String2=0x04,survey point
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
DayXpm="13 13 3 1"   Colormode=16
"!\tc #202020"
"#\tc #FFFFFF"
"  \tc none"
"      !      "
"     !#!     "
"    !#!!     "
"    !#!#!    "
"   !#! !#!   "
"  !#!   !#!  "
" !!!!!!!!!!! "
"     !!!     "
"     !#!     "
"   !!!#!!!   "
"     !#!     "
"     !!!     "
"             "
;1234567890123
[end]
'''
TYP.write_text(typ.rstrip() + typ_add + '\n', encoding='utf-8', newline='\n')

TEST.write_text(r'''from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'
TYP = ROOT / 'styles' / 'uralla.txt'

class TopoMarkerPointTests(unittest.TestCase):
    def test_cairn_and_survey_point_have_dedicated_types(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIn("man_made=cairn {name '${name}' | 'тура'} [0x11506 resolution 24]", points)
        self.assertIn("man_made=survey_point {name '${name}' | '${ref}' | 'геодезический пункт'} [0x11507 resolution 23]", points)

        typ = TYP.read_text(encoding='utf-8')
        for subtype in ('0x06', '0x07'):
            pattern = rf"\[_point\]\s*\nType=0x115\s*\nSubType={subtype}\b[\s\S]*?\[end\]"
            match = re.search(pattern, typ)
            self.assertIsNotNone(match, subtype)
            section = match.group(0)
            self.assertIn('ExtendedLabels=Y', section)
            self.assertIn('FontStyle=NoLabel (invisible)', section)

    def test_unwanted_car_dealer_and_nursing_home_are_absent(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'^amenity=nursing_home(?:\s|$)', points, re.MULTILINE))
        self.assertIsNone(re.search(r'^shop=car(?:\s|$)', points, re.MULTILINE))
        self.assertIn('amenity=car_rental', points)
        self.assertIn('amenity=car_wash', points)

if __name__ == '__main__':
    unittest.main()
''', encoding='utf-8', newline='\n')

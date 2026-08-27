from pathlib import Path

POINTS = Path('styles/uralla/points')
PRIORITY = Path('styles/uralla/inc/priority_points')
LANDUSE = Path('styles/uralla/inc/landuse_points')
TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_topo_marker_points.py')

points = POINTS.read_text(encoding='utf-8')
old_nursing = "amenity=nursing_home [0x2f14 resolution 24]\n"
if points.count(old_nursing) != 1:
    raise SystemExit(f'expected one amenity=nursing_home rule, got {points.count(old_nursing)}')
points = points.replace(old_nursing, '', 1)
POINTS.write_text(points, encoding='utf-8', newline='\n')

priority = PRIORITY.read_text(encoding='utf-8')
old_motor = "(shop=car | shop=car_dealer | shop=car_parts | shop=car_rental | shop=car_repair | shop=car_wrecker | shop=tires | shop=tyres | shop=motorcycle) [0x2f03 resolution 24]"
new_motor = "(shop=car_parts | shop=car_rental | shop=car_repair | shop=car_wrecker | shop=tires | shop=tyres | shop=motorcycle) [0x2f03 resolution 24]"
if priority.count(old_motor) != 1:
    raise SystemExit(f'expected one motor vehicle shop group, got {priority.count(old_motor)}')
priority = priority.replace(old_motor, new_motor, 1)
old_cairn = "man_made=cairn [0x2f18 resolution 23]"
new_cairn = "man_made=cairn { name '${name}' | 'тура' } [0x11506 resolution 23]"
if priority.count(old_cairn) != 1:
    raise SystemExit(f'expected one cairn rule, got {priority.count(old_cairn)}')
priority = priority.replace(old_cairn, new_cairn, 1)
PRIORITY.write_text(priority, encoding='utf-8', newline='\n')

landuse = LANDUSE.read_text(encoding='utf-8')
old_survey = 'man_made=survey_point {name "${name} (${ele})"} [0x6617 resolution 24]'
new_survey = 'man_made=survey_point {name "${name} (${ele})" | "${name}" | "${ref}" | "геодезический пункт"} [0x11508 resolution 24]'
if landuse.count(old_survey) != 1:
    raise SystemExit(f'expected one survey point rule, got {landuse.count(old_survey)}')
landuse = landuse.replace(old_survey, new_survey, 1)
LANDUSE.write_text(landuse, encoding='utf-8', newline='\n')

typ = TYP.read_text(encoding='utf-8')
for subtype in ('0x06', '0x08'):
    if f'Type=0x115\nSubType={subtype}' in typ:
        raise SystemExit(f'0x115{subtype[2:]} already exists in TYP')

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
SubType=0x08
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
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
LANDUSE = ROOT / 'styles' / 'uralla' / 'inc' / 'landuse_points'
TYP = ROOT / 'styles' / 'uralla.txt'

class TopoMarkerPointTests(unittest.TestCase):
    def test_cairn_and_survey_point_have_dedicated_types(self) -> None:
        priority = PRIORITY.read_text(encoding='utf-8')
        landuse = LANDUSE.read_text(encoding='utf-8')
        self.assertIn("man_made=cairn { name '${name}' | 'тура' } [0x11506 resolution 23]", priority)
        self.assertIn('man_made=survey_point {name "${name} (${ele})" | "${name}" | "${ref}" | "геодезический пункт"} [0x11508 resolution 24]', landuse)
        self.assertNotIn('man_made=cairn [0x2f18 resolution 23]', priority)
        self.assertNotIn('man_made=survey_point {name "${name} (${ele})"} [0x6617 resolution 24]', landuse)

        typ = TYP.read_text(encoding='utf-8')
        for subtype in ('0x06', '0x08'):
            pattern = rf"\[_point\]\s*\nType=0x115\s*\nSubType={subtype}\b[\s\S]*?\[end\]"
            match = re.search(pattern, typ)
            self.assertIsNotNone(match, subtype)
            section = match.group(0)
            self.assertIn('ExtendedLabels=Y', section)
            self.assertIn('FontStyle=NoLabel (invisible)', section)

    def test_car_dealer_and_nursing_home_are_not_rendered(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        priority = PRIORITY.read_text(encoding='utf-8')
        self.assertNotIn('amenity=nursing_home', points)
        self.assertNotRegex(priority, r'\bshop=car\b')
        self.assertNotIn('shop=car_dealer', priority)
        self.assertIn('shop=car_parts', priority)
        self.assertIn('shop=car_repair', priority)
        self.assertIn('amenity=car_rental', points)
        self.assertIn('amenity=car_wash', points)

if __name__ == '__main__':
    unittest.main()
''', encoding='utf-8', newline='\n')

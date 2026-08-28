from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
points_path = ROOT / 'styles' / 'uralla' / 'points'
priority_path = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'
typ_path = ROOT / 'styles' / 'uralla.txt'

# 1) Main points: fountain moves from unsupported 0x11502 to ordinary 0x2f19.
points = points_path.read_text(encoding='utf-8')
old_fountain = 'amenity=fountain [0x11502 resolution 23]'
new_fountain = 'amenity=fountain [0x2f19 resolution 23]'
assert points.count(old_fountain) == 1, points.count(old_fountain)
assert new_fountain not in points
points = points.replace(old_fountain, new_fountain, 1)
points_path.write_text(points, encoding='utf-8')

# 2) Priority POIs: rental shares proven bicycle type; parking remains documented but inactive.
# Safety POIs share the existing medical type 0x3002.
priority = priority_path.read_text(encoding='utf-8')
bike_anchor = "shop=bicycle { name '${name}' | 'велосипеды' } [0x2f18 resolution 23]\n"
assert priority.count(bike_anchor) == 1, priority.count(bike_anchor)
bike_add = bike_anchor + "amenity=bicycle_rental { name '${name}' | 'прокат велосипедов' } [0x2f18 resolution 24]\n# Bicycle parking is intentionally not rendered for now.\n# amenity=bicycle_parking { name '${name}' | 'велопарковка' } [0x2f18 resolution 24]\n"
assert 'amenity=bicycle_rental' not in priority
assert 'amenity=bicycle_parking' not in priority
priority = priority.replace(bike_anchor, bike_add, 1)

em_anchor = "(amenity=emergency_phone | emergency=phone) [0x2f12 resolution 23]\n"
assert priority.count(em_anchor) == 1, priority.count(em_anchor)
em_add = em_anchor + "(emergency=defibrillator | amenity=defibrillator) { name '${name}' | 'дефибриллятор' } [0x3002 resolution 24]\nemergency=first_aid_kit { name '${name}' | 'аптечка' } [0x3002 resolution 24]\n"
assert 'defibrillator' not in priority
assert 'first_aid_kit' not in priority
priority = priority.replace(em_anchor, em_add, 1)
priority_path.write_text(priority, encoding='utf-8')

# 3) TYP: migrate the existing fountain block byte-for-byte in appearance,
# changing only Garmin type/subtype to ordinary 0x02f/0x19.
typ = typ_path.read_text(encoding='utf-8')
block_re = re.compile(r'(?ms)^\[_point\]\nType=0x115\nSubType=0x02\n.*?^\[end\]')
matches = list(block_re.finditer(typ))
assert len(matches) == 1, len(matches)
old_block = matches[0].group(0)
assert 'String1=0x19,фонтан' in old_block
assert 'String2=0x04,fountain' in old_block
assert 'ExtendedLabels=N' in old_block
assert 'FontStyle=NoLabel' not in old_block
assert not re.search(r'(?ms)^\[_point\]\nType=0x02f\nSubType=0x19\n', typ)
new_block = old_block.replace('Type=0x115\nSubType=0x02\n', 'Type=0x02f\nSubType=0x19\n', 1)
typ = typ[:matches[0].start()] + new_block + typ[matches[0].end():]
typ_path.write_text(typ, encoding='utf-8')

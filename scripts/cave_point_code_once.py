from pathlib import Path
import re

PRIORITY = Path('styles/uralla/inc/priority_points')
TYP = Path('styles/uralla.txt')
TEST = Path('tests/test_cave_waterfall_points.py')

priority = PRIORITY.read_text(encoding='utf-8')
priority = priority.replace("[0x11602 resolution 23]", "[0x6608 resolution 23]")
priority = priority.replace("[0x11602 resolution 24]", "[0x6608 resolution 24]")
if '0x11602' in priority:
    raise SystemExit('old cave point code still present in priority_points')
PRIORITY.write_text(priority, encoding='utf-8', newline='\n')

typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(r'(?ms)^\[_point\]\nType=0x116\nSubType=0x02\n.*?^\[end\]\n?')
match = pattern.search(typ)
if not match:
    raise SystemExit('cave TYP 0x11602 not found')
section = match.group(0)
section = section.replace('Type=0x116\nSubType=0x02', 'Type=0x066\nSubType=0x08', 1)
section = section.replace('FontStyle=NoLabel (invisible)', 'FontStyle=SmallFont', 1)
typ = typ[:match.start()] + section + typ[match.end():]
TYP.write_text(typ, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
test = test.replace('0x11602 resolution 23', '0x6608 resolution 23')
test = test.replace('0x11602 resolution 24', '0x6608 resolution 24')
TEST.write_text(test, encoding='utf-8', newline='\n')

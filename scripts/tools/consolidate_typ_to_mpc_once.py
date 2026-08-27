from pathlib import Path
import re

p = Path('styles/uralla.txt')
text = p.read_text(encoding='utf-8')

HEADER = '; -*- coding: utf-8 -*-'
if not text.startswith(HEADER):
    text = HEADER + '\n' + text.lstrip('\ufeff\n')

roles = {
    '0x07': 'forest-road-good-far + pedestrian-cycleway-far',
    '0x0a': 'forest-road-good-near',
    '0x12': 'forest-road-bad-far',
    '0x0e': 'pedestrian-cycleway-near',
    '0x0b': 'foot-bicycle-trail-far',
    '0x16': 'foot-bicycle-trail-near',
}

for typ, role in roles.items():
    pat = re.compile(r'(\[_line\]\nType=' + re.escape(typ) + r'\n)(?!;URALLA_ROLE:)', re.I)
    text, n = pat.subn(r'\1;URALLA_ROLE: ' + role + '\n', text, count=1)
    if n != 1 and f'Type={typ}\n;URALLA_ROLE: {role}\n' not in text:
        raise SystemExit(f'cannot annotate canonical MPC type {typ}')

# Keep only the one genuinely unique semantic custom line: 0x13504.
for typ in ('0x13501', '0x13502', '0x13503', '0x13505', '0x13506', '0x13507'):
    pat = re.compile(r'\n?\[_line\]\nType=' + re.escape(typ) + r'\n.*?\n\[end\]\n?', re.S | re.I)
    text, n = pat.subn('\n', text, count=1)
    if n != 1:
        raise SystemExit(f'cannot remove temporary role type {typ}')

# Give the surviving custom role an explicit canonical comment.
text = re.sub(
    r'(\[_line\]\nType=0x13504\n)(?:;URALLA_ROLE:.*\n)?',
    r'\1;URALLA_ROLE: forest-road-bad-near\n',
    text,
    count=1,
    flags=re.I,
)

p.write_text(text, encoding='utf-8', newline='\n')
print('consolidated semantic road/trail visuals onto MPC types; kept only 0x13504')

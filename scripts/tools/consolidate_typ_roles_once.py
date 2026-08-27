from pathlib import Path
import re

p = Path('styles/uralla.txt')
text = p.read_text(encoding='utf-8')

HEADER = '; -*- coding: utf-8 -*-'
if not text.startswith(HEADER):
    text = HEADER + '\n' + text.lstrip('\ufeff\n')

# Drop the malformed obsolete role tail left from the first generated block.
text = re.sub(r'\[end\]bType=0x08\n; URALLA_ROLE: foot-trail-near.*\Z', '[end]\n', text, flags=re.S)

# Extract the manually designed combined 0x135xx sections.
pat = re.compile(r'\[_line\]\nType=(0x135[0-9a-fA-F]{2})\n.*?\n\[end\]', re.S)
blocks = {m.group(1).lower(): m.group(0) for m in pat.finditer(text)}
required = [f'0x135{i:02x}' for i in range(1, 11)]
missing = [x for x in required if x not in blocks]
if missing:
    raise SystemExit(f'missing role blocks before consolidation: {missing}')

# Keep user-designed visuals, but collapse visually identical roles.
# New canonical sequence:
# 01 good-road-far + pedestrian/cycleway-far   <- old 01
# 02 good-road-near                             <- old 02
# 03 bad-road-far                               <- old 03
# 04 bad-road-near                              <- old 04
# 05 pedestrian/cycleway-near                   <- old 06
# 06 foot/bicycle-trail-far                     <- old 07
# 07 foot/bicycle-trail-near                    <- old 08
roles = [
    ('0x13501', '0x13501', 'forest-road-good-far + pedestrian-cycleway-far'),
    ('0x13502', '0x13502', 'forest-road-good-near'),
    ('0x13503', '0x13503', 'forest-road-bad-far'),
    ('0x13504', '0x13504', 'forest-road-bad-near'),
    ('0x13505', '0x13506', 'pedestrian-cycleway-near'),
    ('0x13506', '0x13507', 'foot-bicycle-trail-far'),
    ('0x13507', '0x13508', 'foot-bicycle-trail-near'),
]

def canonical(dst, src, role):
    b = blocks[src]
    b = re.sub(r'^Type=0x135[0-9a-fA-F]{2}$', f'Type={dst}', b, flags=re.M)
    b = re.sub(r'^;GRMN_TYPE:.*$', f';URALLA_ROLE: {role}', b, count=1, flags=re.M)
    return b

new_block = '\n\n'.join(canonical(*r) for r in roles)

# Replace the entire current manually-designed 10-section run with the 7 canonical sections.
first = text.find('[_line]\nType=0x13501\n')
last_match = list(pat.finditer(text))[-1]
if first < 0:
    raise SystemExit('cannot locate 0x13501 block')
end = last_match.end()
text = text[:first] + new_block + text[end:]

p.write_text(text, encoding='utf-8', newline='\n')
print('consolidated road/trail TYP roles: 10 -> 7')

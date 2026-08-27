from pathlib import Path
import re

LINES = Path('styles/uralla/lines')
TYP = Path('styles/uralla.txt')

lines = LINES.read_text(encoding='utf-8')
old = """# highway=road has unknown physical/classification semantics; keep only the routing helper
# and let the conservative generic highway fallback render it at resolution 24.
highway=road { add mkgmap:dead-end-check = false }

"""
if lines.count(old) != 1:
    raise SystemExit(f'expected one highway=road helper block, got {lines.count(old)}')
lines = lines.replace(old, '', 1)
anchor = "# Special-purpose highways must not become generic motor-routing roads when access tags are incomplete.\n"
new = """# highway=road has unknown physical/classification semantics. Keep the routing helper
# before the fallback so it executes, then let the generic fallback render at resolution 24.
highway=road { add mkgmap:dead-end-check = false }

"""
if anchor not in lines:
    raise SystemExit('special highway fallback anchor not found')
LINES.write_text(lines.replace(anchor, new + anchor, 1), encoding='utf-8', newline='\n')

typ = TYP.read_text(encoding='utf-8')
pattern = re.compile(r'(?ms)^\[_line\]\s*\nType=0x05\s*\n.*?^\[end\]\s*\n')
matches = list(pattern.finditer(typ))
if len(matches) != 1:
    raise SystemExit(f'expected one _line Type=0x05 section, got {len(matches)}')
start, end = matches[0].span()
typ = typ[:start] + typ[end:]
TYP.write_text(typ, encoding='utf-8', newline='\n')

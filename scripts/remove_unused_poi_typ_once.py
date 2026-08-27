from pathlib import Path
import re

TYP = Path('styles/uralla.txt')
text = TYP.read_text(encoding='utf-8')

section_re = re.compile(r'(?ms)^\[_point\]\n.*?^\[end\]\n?')
removed = []


def combined_code(section: str):
    tm = re.search(r'^Type=(0x[0-9A-Fa-f]+)\s*$', section, re.MULTILINE)
    if not tm:
        return None
    t = int(tm.group(1), 16)
    sm = re.search(r'^SubType=(0x[0-9A-Fa-f]+)\s*$', section, re.MULTILINE)
    if sm:
        return (t << 8) | int(sm.group(1), 16)
    return t


def repl(match: re.Match[str]) -> str:
    section = match.group(0)
    code = combined_code(section)
    if code in (0x2F14, 0x2F18):
        removed.append(code)
        return ''
    return section

new_text = section_re.sub(repl, text)
if sorted(removed) != [0x2F14, 0x2F18]:
    raise SystemExit(f'expected to remove 0x2f14 and 0x2f18, got {[hex(x) for x in removed]}')
TYP.write_text(new_text, encoding='utf-8', newline='\n')

from pathlib import Path

TYP = Path("styles/uralla.txt")
HEADER = "; -*- coding: utf-8 -*-"

raw = TYP.read_bytes()
text = raw.decode("cp1251")
if not text.startswith(HEADER):
    text = HEADER + "\n" + text.lstrip("\ufeff")
TYP.write_text(text, encoding="utf-8", newline="\n")
print("converted styles/uralla.txt from cp1251 to utf-8")

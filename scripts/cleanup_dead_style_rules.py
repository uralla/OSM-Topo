#!/usr/bin/env python3
"""Remove proven-unreachable style rules and re-prune direct TYP source."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla"
POINTS = STYLE / "points"
LANDUSE_POINTS = STYLE / "inc" / "landuse_points"
TYP = ROOT / "styles" / "uralla.txt"

TYPE_RE = re.compile(r"\[\s*(0x[0-9a-fA-F]+)\b")
INCLUDE_RE = re.compile(r"^\s*include\s+'([^']+)'\s*;", re.MULTILINE)
SECTION_RE = re.compile(r"(?ims)^\[(?P<kind>_point|_line|_polygon)\]\s*\r?\n.*?^\[end\]\s*(?:\r?\n)?")
DRAW_RE = re.compile(r"(?ims)^\[_drawOrder\]\s*\r?\n.*?^\[end\]\s*(?:\r?\n)?")


def active_source(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(line.split("#", 1)[0])
    return "\n".join(out)


def closure(entry: Path) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        if not path.is_file():
            raise RuntimeError(f"missing include: {path}")
        seen.add(path)
        result.append(path)
        active = active_source(path.read_text(encoding="utf-8"))
        for rel in INCLUDE_RE.findall(active):
            visit(STYLE / rel)

    visit(entry)
    return result


def used_types(entry: str) -> set[int]:
    result: set[int] = set()
    for path in closure(STYLE / entry):
        active = active_source(path.read_text(encoding="utf-8"))
        result.update(int(code, 16) for code in TYPE_RE.findall(active))
    return result


def detect_encoding(raw: bytes) -> str:
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        raw.decode("cp1251")
        return "cp1251"


def section_code(kind: str, section: str) -> int:
    tm = re.search(r"(?im)^Type\s*=\s*0x([0-9a-f]+)\b", section)
    if tm is None:
        raise RuntimeError(f"{kind} section without Type")
    value = int(tm.group(1), 16)
    if kind == "_point":
        sm = re.search(r"(?im)^SubType\s*=\s*0x([0-9a-f]+)\b", section)
        if sm:
            value = (value << 8) | int(sm.group(1), 16)
    return value


def label(section: str) -> str:
    for pattern in (r"(?im)^String1\s*=\s*[^,]*,(.*)$", r"(?im)^String2\s*=\s*[^,]*,(.*)$"):
        m = re.search(pattern, section)
        if m:
            return m.group(1).strip()[:60]
    return ""


def patch_points() -> None:
    text = POINTS.read_text(encoding="utf-8")
    start_marker = "###place=city & population > 999999 & name=*"
    end_marker = "place=locality & mkgmap:area2poi!=true\t[0x11504 resolution 22]"
    if start_marker not in text or end_marker not in text:
        raise RuntimeError("legacy settlement fallback block markers not found")
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    while end < len(text) and text[end] in "\r\n":
        end += 1
    replacement = "# Settlement rendering is defined entirely in inc/place_points.\n\n"
    text = text[:start] + replacement + text[end:]
    POINTS.write_text(text, encoding="utf-8", newline="")


def patch_landuse_points() -> None:
    text = LANDUSE_POINTS.read_text(encoding="utf-8")
    old = (
        "# Edge 705 displays 0x650a,0x6511,0x6512,0x6513,0x6603,0x6614 as hollow white circles, no menu\n"
        "natural=cave_entrance [0x6601 resolution 23]\n"
    )
    if old not in text:
        raise RuntimeError("shadowed cave_entrance fallback not found")
    text = text.replace(
        old,
        "# cave_entrance is handled earlier in inc/priority_points as 0x11602.\n",
        1,
    )
    LANDUSE_POINTS.write_text(text, encoding="utf-8", newline="")


def prune_typ() -> None:
    used = {
        "_point": used_types("points"),
        "_line": used_types("lines"),
        "_polygon": used_types("polygons"),
    }
    raw = TYP.read_bytes()
    enc = detect_encoding(raw)
    text = raw.decode(enc)
    removed: list[tuple[str, int, str]] = []

    matches = list(SECTION_RE.finditer(text))
    for m in reversed(matches):
        kind = m.group("kind").lower()
        code = section_code(kind, m.group(0))
        if code in used[kind]:
            continue
        removed.append((kind, code, label(m.group(0))))
        text = text[:m.start()] + text[m.end():]

    dm = list(DRAW_RE.finditer(text))
    if len(dm) != 1:
        raise RuntimeError(f"expected one _drawOrder, got {len(dm)}")
    m = dm[0]
    kept = []
    draw_removed = 0
    for line in m.group(0).splitlines(keepends=True):
        tm = re.match(r"(?i)^\s*Type\s*=\s*0x([0-9a-f]+)\s*,", line)
        if tm and int(tm.group(1), 16) not in used["_polygon"]:
            draw_removed += 1
            continue
        kept.append(line)
    text = text[:m.start()] + "".join(kept) + text[m.end():]
    text = re.sub(r"(?:\r?\n){4,}", "\n\n\n", text)
    TYP.write_bytes(text.encode(enc))

    print(f"TYP encoding preserved: {enc}")
    print(f"Additional TYP sections removed: {len(removed)}")
    for kind, code, name in sorted(removed):
        print(f"  {kind} 0x{code:x} {name}")
    print(f"Additional drawOrder entries removed: {draw_removed}")


def main() -> None:
    patch_points()
    patch_landuse_points()
    prune_typ()
    print("Removed proven-unreachable settlement/cave fallbacks")


if __name__ == "__main__":
    main()

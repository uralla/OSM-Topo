#!/usr/bin/env python3
"""Remove implicit night palettes from TYP line XPMs, preserving day rendering.

mkgmap's TYP syntax stores day/night alternatives inside a single Xpm palette for
lines.  This one-shot migration keeps the day palette and bitmap exactly, removes
only the alternate night colours, and leaves points/polygons untouched.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"

SECTION_RE = re.compile(r"(?ims)^\[(_point|_line|_polygon)\]\s*\n.*?^\[end\]\s*(?:\n|$)")
XPM_RE = re.compile(r'(?im)^Xpm="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"([^\n]*)$')
TYPE_RE = re.compile(r"(?im)^Type=(0x[0-9a-f]+)\b")
SUB_RE = re.compile(r"(?im)^SubType=(0x[0-9a-f]+)\b")
BORDER_RE = re.compile(r"(?im)^BorderWidth\s*=\s*(\d+)\s*$")
LINEWIDTH_RE = re.compile(r"(?im)^LineWidth\s*=\s*(\d+)\s*$")


def detect_encoding(raw: bytes) -> str:
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        raw.decode("cp1251")
        return "cp1251"


def element_id(block: str) -> str:
    tm = TYPE_RE.search(block)
    sm = SUB_RE.search(block)
    result = tm.group(1) if tm else "?"
    if sm:
        result += "/" + sm.group(1)
    return result


def xpm_parts(block: str) -> tuple[re.Match[str], list[str], int, int, int, int, int]:
    hm = XPM_RE.search(block)
    if not hm:
        raise RuntimeError("line section has no Xpm")
    w, h, colors, cpp = map(int, hm.groups()[:4])
    lines = block.splitlines()
    header_index = next(i for i, line in enumerate(lines) if XPM_RE.match(line))
    return hm, lines, header_index, w, h, colors, cpp


def border_width(block: str) -> int:
    m = BORDER_RE.search(block)
    return int(m.group(1)) if m else 0


def palette_symbol(line: str, cpp: int) -> str:
    # Palette rows are quoted strings; the first cpp characters inside the quote
    # are the pixel key. Spaces are valid keys and must be preserved.
    if not line.startswith('"') or len(line) < 1 + cpp:
        raise RuntimeError(f"invalid palette row: {line!r}")
    return line[1 : 1 + cpp]


def day_palette_count(block: str, h: int, colors: int) -> int:
    border = border_width(block)
    if h > 0:
        # Garmin line bitmaps use two colours for one day/night-shared bitmap and
        # four when a second (night) pair is present.
        return min(colors, 2)
    if border > 0:
        # Solid bordered line: main + border are the day pair.
        return min(colors, 2)
    # Solid unbordered line: a second colour is the night alternative.
    return min(colors, 1)


def day_signature(block: str) -> tuple[object, ...]:
    hm, lines, hi, w, h, colors, cpp = xpm_parts(block)
    keep = day_palette_count(block, h, colors)
    palette = tuple(lines[hi + 1 : hi + 1 + keep])
    bitmap = tuple(lines[hi + 1 + colors : hi + 1 + colors + h])
    lw = LINEWIDTH_RE.search(block)
    bw = BORDER_RE.search(block)
    return (
        element_id(block),
        w,
        h,
        cpp,
        palette,
        bitmap,
        int(lw.group(1)) if lw else None,
        int(bw.group(1)) if bw else 0,
        hm.group(5).strip(),
    )


def patch_line(block: str) -> tuple[str, str | None]:
    hm, lines, hi, w, h, colors, cpp = xpm_parts(block)
    border = border_width(block)

    target = colors
    reason: str | None = None
    if h > 0 and colors == 4:
        target = 2
        reason = "bitmap day/night pair"
    elif h == 0 and colors == 4:
        target = 2
        reason = "solid bordered day/night pair"
    elif h == 0 and colors == 2 and border == 0:
        target = 1
        reason = "solid unbordered day/night pair"

    if target == colors:
        return block, None

    if colors not in {2, 4}:
        raise RuntimeError(f"unexpected night palette size for {element_id(block)}: {colors}")

    # For bitmap lines the pixel matrix must use only the day keys. Garmin switches
    # those keys to the alternate night pair internally; the night keys themselves
    # should not occur in the matrix.
    if h > 0:
        palette = lines[hi + 1 : hi + 1 + colors]
        day_keys = {palette_symbol(row, cpp) for row in palette[:target]}
        bitmap = lines[hi + 1 + colors : hi + 1 + colors + h]
        for row in bitmap:
            if not row.startswith('"'):
                raise RuntimeError(f"invalid bitmap row in {element_id(block)}: {row!r}")
            pixels = row[1:-1]
            if len(pixels) != w * cpp:
                raise RuntimeError(f"bitmap width mismatch in {element_id(block)}")
            for pos in range(0, len(pixels), cpp):
                if pixels[pos : pos + cpp] not in day_keys:
                    raise RuntimeError(
                        f"night-only palette key used by bitmap in {element_id(block)}"
                    )

    new_header = re.sub(
        r'Xpm="\d+\s+\d+\s+\d+\s+\d+"',
        f'Xpm="{w} {h} {target} {cpp}"',
        lines[hi],
        count=1,
    )
    new_lines = (
        lines[:hi]
        + [new_header]
        + lines[hi + 1 : hi + 1 + target]
        + lines[hi + 1 + colors :]
    )
    newline = "\r\n" if "\r\n" in block else "\n"
    suffix = newline if block.endswith(("\n", "\r\n")) else ""
    return newline.join(new_lines) + suffix, reason


def main() -> None:
    raw = TYP.read_bytes()
    enc = detect_encoding(raw)
    text = raw.decode(enc)

    point_before = [m.group(0) for m in SECTION_RE.finditer(text) if m.group(1) == "_point"]
    polygon_before = [m.group(0) for m in SECTION_RE.finditer(text) if m.group(1) == "_polygon"]
    line_before = [m.group(0) for m in SECTION_RE.finditer(text) if m.group(1) == "_line"]
    signatures_before = [day_signature(block) for block in line_before if XPM_RE.search(block)]

    changes: list[tuple[str, str]] = []
    pieces: list[str] = []
    last = 0
    for match in SECTION_RE.finditer(text):
        pieces.append(text[last : match.start()])
        block = match.group(0)
        if match.group(1) == "_line" and XPM_RE.search(block):
            block, reason = patch_line(block)
            if reason:
                changes.append((element_id(match.group(0)), reason))
        pieces.append(block)
        last = match.end()
    pieces.append(text[last:])
    result = "".join(pieces)

    point_after = [m.group(0) for m in SECTION_RE.finditer(result) if m.group(1) == "_point"]
    polygon_after = [m.group(0) for m in SECTION_RE.finditer(result) if m.group(1) == "_polygon"]
    line_after = [m.group(0) for m in SECTION_RE.finditer(result) if m.group(1) == "_line"]
    signatures_after = [day_signature(block) for block in line_after if XPM_RE.search(block)]

    if point_after != point_before:
        raise RuntimeError("point TYP sections changed")
    if polygon_after != polygon_before:
        raise RuntimeError("polygon TYP sections changed")
    if signatures_after != signatures_before:
        raise RuntimeError("day line rendering changed")

    TYP.write_bytes(result.encode(enc))
    print("encoding:", enc)
    print("implicit night palettes removed:", len(changes))
    for typ, reason in changes:
        print(f"  {typ}: {reason}")
    print("size:", len(raw), "->", TYP.stat().st_size)


if __name__ == "__main__":
    main()

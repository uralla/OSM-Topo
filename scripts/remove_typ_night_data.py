#!/usr/bin/env python3
"""One-shot removal of explicit night-only data from the direct TYP source."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"


def encoding_for(raw: bytes) -> str:
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        raw.decode("cp1251")
        return "cp1251"


def xpm_blocks(lines: list[str], field: str) -> list[bytes]:
    rx = re.compile(rf'^\s*{re.escape(field)}="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"', re.I)
    blocks: list[bytes] = []
    i = 0
    while i < len(lines):
        m = rx.match(lines[i])
        if not m:
            i += 1
            continue
        _width, height, colors, _cpp = map(int, m.groups())
        size = 1 + colors + height
        block = "\n".join(lines[i : i + size]).encode("utf-8")
        blocks.append(hashlib.sha256(block).digest())
        i += size
    return blocks


def main() -> None:
    raw = TYP.read_bytes()
    enc = encoding_for(raw)
    text = raw.decode(enc)
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()

    day_xpm_before = xpm_blocks(lines, "DayXpm")
    xpm_before = xpm_blocks(lines, "Xpm")
    day_colors_before = [
        line for line in lines if re.match(r"\s*DaycustomColor\s*[:=]", line, re.I)
    ]

    removed_night_xpm = 0
    removed_night_color = 0
    removed_editor_mode = 0
    out: list[str] = []
    i = 0
    night_rx = re.compile(r'^\s*NightXpm="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"', re.I)
    while i < len(lines):
        line = lines[i]
        m = night_rx.match(line)
        if m:
            _width, height, colors, _cpp = map(int, m.groups())
            size = 1 + colors + height
            if i + size > len(lines):
                raise RuntimeError("NightXpm block extends past end of file")
            i += size
            removed_night_xpm += 1
            continue
        if re.match(r"\s*NightcustomColor\s*[:=]", line, re.I):
            removed_night_color += 1
            i += 1
            continue
        if re.match(r"\s*CustomColor\s*=\s*DayAndNight\s*$", line, re.I):
            removed_editor_mode += 1
            i += 1
            continue
        out.append(line)
        i += 1

    result = newline.join(out) + newline
    result_lines = result.splitlines()

    if re.search(r"(?im)^\s*Night(?:Xpm|customColor)\b", result):
        raise RuntimeError("explicit NightXpm/NightcustomColor remains")
    if re.search(r"(?im)^\s*CustomColor\s*=\s*DayAndNight\s*$", result):
        raise RuntimeError("DayAndNight editor marker remains")
    if xpm_blocks(result_lines, "DayXpm") != day_xpm_before:
        raise RuntimeError("DayXpm graphics changed")
    if xpm_blocks(result_lines, "Xpm") != xpm_before:
        raise RuntimeError("day/common Xpm graphics changed")
    day_colors_after = [
        line for line in result_lines if re.match(r"\s*DaycustomColor\s*[:=]", line, re.I)
    ]
    if day_colors_after != day_colors_before:
        raise RuntimeError("DaycustomColor values changed")

    TYP.write_bytes(result.encode(enc))
    print("encoding:", enc)
    print("removed NightXpm:", removed_night_xpm)
    print("removed NightcustomColor:", removed_night_color)
    print("removed CustomColor=DayAndNight:", removed_editor_mode)
    print("size:", len(raw), "->", TYP.stat().st_size)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""One-shot repository migration for already agreed style/TYP decisions.

This script is intentionally self-cleaning through the companion GitHub Action.
It is NOT part of the build pipeline. The final repository keeps styles/uralla.txt
as the direct authoritative TYP source.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / "styles" / "uralla" / "lines"
TYP = ROOT / "styles" / "uralla.txt"


def require_replace(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 0:
        if new in text:
            return text
        raise RuntimeError(f"{label}: expected source text not found")
    if count != 1:
        raise RuntimeError(f"{label}: expected one source occurrence, found {count}")
    return text.replace(old, new, 1)


def section_pattern(kind: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?ims)^\[{re.escape(kind)}\][ \t]*\r?\n.*?^\[end\][ \t]*(?:\r?\n)?"
    )


def typed_sections(text: str, kind: str, type_code: str) -> list[re.Match[str]]:
    type_re = re.compile(rf"(?im)^Type={re.escape(type_code)}(?:\b|$)")
    return [m for m in section_pattern(kind).finditer(text) if type_re.search(m.group(0))]


def get_one_section(text: str, kind: str, type_code: str) -> str:
    matches = typed_sections(text, kind, type_code)
    if len(matches) != 1:
        raise RuntimeError(
            f"{kind} {type_code}: expected exactly one section, found {len(matches)}"
        )
    return matches[0].group(0)


def remove_sections(text: str, kind: str, type_code: str) -> str:
    matches = typed_sections(text, kind, type_code)
    for m in reversed(matches):
        text = text[: m.start()] + text[m.end() :]
    return text


def rename_line_type(text: str, old_type: str, new_type: str) -> str:
    old_matches = typed_sections(text, "_line", old_type)
    new_matches = typed_sections(text, "_line", new_type)

    # Idempotent rerun: already migrated and old slot absent.
    if not old_matches:
        if len(new_matches) == 1:
            return text
        raise RuntimeError(
            f"line {old_type}->{new_type}: old absent, new count={len(new_matches)}"
        )

    if len(old_matches) != 1:
        raise RuntimeError(
            f"line {old_type}->{new_type}: expected one old section, found {len(old_matches)}"
        )

    # A pre-existing target would create an ambiguous duplicate. Remove it; the
    # current old section is the authoritative visual source and its graphics/colors
    # are preserved byte-for-byte apart from the Type line.
    text = remove_sections(text, "_line", new_type)
    old_matches = typed_sections(text, "_line", old_type)
    old = old_matches[0]
    block = old.group(0)
    migrated = re.sub(
        rf"(?im)^Type={re.escape(old_type)}(?:\b|$)",
        f"Type={new_type}",
        block,
        count=1,
    )
    return text[: old.start()] + migrated + text[old.end() :]


def patch_lines() -> None:
    text = LINES.read_text(encoding="utf-8")

    # Old polygon/line slot collisions: keep polygon slots 0x10f09/0x10f05 for
    # polygons; move the corresponding line semantics to dedicated line slots.
    text = require_replace(
        text,
        "natural=tree_row & length()>100 [0x10f09 resolution 23-24]",
        "natural=tree_row & area!=yes & length()>100 [0x10f1a resolution 23-24]",
        "tree_row line slot",
    )
    text = require_replace(
        text,
        "railway=rail & service=* & length()>500 [0x10f05 resolution 23-23 continue]\n"
        "railway=rail & service=* [0x10f05 resolution 24]",
        "railway=rail & service=* & length()>500 [0x10f1b resolution 23-23 continue]\n"
        "railway=rail & service=* [0x10f1b resolution 24]",
        "service railway line slot",
    )

    # [CUSTOM/АВТОРСКОЕ] Marked hiking/bicycle/mtb route members are visible
    # exactly one zoom step farther. Only the single missing resolution is emitted,
    # so existing close-zoom rules stay unchanged and cannot double-render.
    marker = "# [CUSTOM/АВТОРСКОЕ] Marked route members: one extra LOD step."
    if marker not in text:
        anchor = (
            "highway=living_street [0x06 road_class=0 road_speed=1 resolution 23]\n\n"
            "highway=bridleway [0x16 road_class=0 road_speed=0 resolution 24]"
        )
        trail_block = (
            "highway=living_street [0x06 road_class=0 road_speed=1 resolution 23]\n\n"
            f"{marker}\n"
            "# Emit only the additional farther level; normal rules below render the usual levels.\n"
            "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x07 resolution 21-21 continue]\n"
            "mkgmap:trail_name=* & bicycle=yes & highway=path & length()>100 [0x0b resolution 21-21 continue]\n"
            "mkgmap:trail_name=* & highway=footway & length()>100 [0x07 resolution 21-21 continue]\n"
            "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x0b resolution 22-22 continue]\n"
            "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x12 resolution 21-21 continue]\n"
            "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x07 resolution 20-20 continue]\n"
            "mkgmap:trail_name=* & highway=bridleway & length()>100 [0x16 resolution 23-23 continue]\n\n"
            "highway=bridleway [0x16 road_class=0 road_speed=0 resolution 24]"
        )
        text = require_replace(text, anchor, trail_block, "marked-route LOD block")

    LINES.write_text(text, encoding="utf-8", newline="")


def detect_typ_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    # Current historical source is Windows-1251, but keep this migration robust if
    # it has already been converted to UTF-8 before the action runs.
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        raw.decode("cp1251")
        return "cp1251"


def patch_draw_order(text: str) -> str:
    pattern = re.compile(r"(?ims)^\[_drawOrder\][ \t]*\r?\n.*?^\[end\][ \t]*(?:\r?\n)?")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"_drawOrder: expected one section, found {len(matches)}")
    match = matches[0]
    block = match.group(0)
    # The second 0x10f09 entry is the historical duplicate. Keep 0x10f09,1.
    block = re.sub(r"(?im)^Type=0x10f09,10[ \t]*\r?\n", "", block)
    return text[: match.start()] + block + text[match.end() :]


def patch_tunnel_section(text: str, nl: str) -> str:
    matches = typed_sections(text, "_line", "0x10e04")
    if len(matches) != 1:
        raise RuntimeError(f"tunnel 0x10e04: expected one section, found {len(matches)}")
    m = matches[0]
    block = nl.join(
        [
            "[_line]",
            "Type=0x10e04",
            "; [CUSTOM/АВТОРСКОЕ] единый тоннель / unified tunnel",
            "UseOrientation=N",
            "LineWidth=3",
            'Xpm="0 0 1 0"',
            '"1 c #626262"',
            "String1=0x19,туннель",
            "String2=0x04,tunnel",
            "ExtendedLabels=Y",
            "FontStyle=SmallFont",
            "CustomColor=No",
            "[end]",
            "",
        ]
    )
    return text[: m.start()] + block + text[m.end() :]


def patch_typ() -> None:
    raw = TYP.read_bytes()
    encoding = detect_typ_encoding(raw)
    text = raw.decode(encoding)
    nl = "\r\n" if "\r\n" in text else "\n"

    # Guard already visually verified pier definitions from accidental edits.
    pier_line_before = get_one_section(text, "_line", "0x10f07")
    pier_polygon_before = get_one_section(text, "_polygon", "0x10f11")

    text = patch_draw_order(text)

    # Preserve the CURRENT graphics and colors exactly while moving line semantics
    # away from polygon-owned numeric slots.
    text = rename_line_type(text, "0x10f09", "0x10f1a")
    text = rename_line_type(text, "0x10f05", "0x10f1b")

    # Final user decision for tunnels: one solid grey line for road/rail tunnels.
    text = patch_tunnel_section(text, nl)

    # Night-mode cleanup and new cave/debris icons are deliberately NOT part of this
    # migration: the later master review leaves those for a separate visual stage.

    if get_one_section(text, "_line", "0x10f07") != pier_line_before:
        raise RuntimeError("pier line section changed unexpectedly")
    if get_one_section(text, "_polygon", "0x10f11") != pier_polygon_before:
        raise RuntimeError("pier polygon section changed unexpectedly")

    if typed_sections(text, "_line", "0x10f09"):
        raise RuntimeError("old line 0x10f09 still present")
    if typed_sections(text, "_line", "0x10f05"):
        raise RuntimeError("old line 0x10f05 still present")
    if len(typed_sections(text, "_line", "0x10f1a")) != 1:
        raise RuntimeError("new line 0x10f1a missing/duplicated")
    if len(typed_sections(text, "_line", "0x10f1b")) != 1:
        raise RuntimeError("new line 0x10f1b missing/duplicated")

    TYP.write_bytes(text.encode(encoding))
    print(f"Patched {TYP.relative_to(ROOT)} preserving encoding {encoding}")


def main() -> None:
    patch_lines()
    patch_typ()
    print("Applied agreed style/TYP master decisions")


if __name__ == "__main__":
    main()

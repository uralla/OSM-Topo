#!/usr/bin/env python3
"""Audit Garmin type usage in the mkgmap style against the TYP source.

The style uses combined hexadecimal codes (for example 0x1341f), while the
TYP source represents extended codes as Type=0x134 + SubType=0x1f.  This tool
normalizes both forms before comparing them.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import sys


TYPE_RE = re.compile(r"\[(0x[0-9a-fA-F]+)\b")
INCLUDE_RE = re.compile(r"^\s*include\s+['\"]([^'\"]+)['\"]\s*;?\s*$")
SECTION_RE = re.compile(r"^\s*\[_(point|line|polygon)\]\s*$", re.IGNORECASE)
FIELD_RE = re.compile(r"^\s*(Type|SubType)\s*=\s*(0x[0-9a-fA-F]+)\s*$", re.IGNORECASE)
END_RE = re.compile(r"^\s*\[end\]\s*$", re.IGNORECASE)

STYLE_ENTRYPOINTS = {
    "point": "points",
    "line": "lines",
    "polygon": "polygons",
}


def split_style_code(code: str) -> tuple[int, int]:
    """Convert a mkgmap combined code into TYP Type/SubType components."""
    value = int(code, 16)
    if value <= 0xFF:
        return value, 0
    return value >> 8, value & 0xFF


def format_code(code: tuple[int, int]) -> str:
    type_id, subtype = code
    if subtype:
        return f"0x{type_id:x}/0x{subtype:02x}"
    return f"0x{type_id:x}"


def is_extended_custom(code: tuple[int, int]) -> bool:
    """Return true for custom/extended Garmin types that require TYP support."""
    type_id, _ = code
    return type_id > 0xFF


def _active_text(text: str) -> str:
    """Drop comments while preserving multiline style expressions."""
    active: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Style comments are line comments in this project. Keep '#' inside
        # quoted labels untouched rather than trying to implement a full lexer.
        active.append(line)
    return "\n".join(active)


def collect_style_codes(style_root: Path, entrypoint: str) -> set[tuple[int, int]]:
    """Collect active Garmin codes reachable from one style entrypoint."""
    seen: set[Path] = set()
    codes: set[tuple[int, int]] = set()

    def visit(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        text = path.read_text(encoding="utf-8")
        active = _active_text(text)
        for match in TYPE_RE.finditer(active):
            codes.add(split_style_code(match.group(1)))
        for line in active.splitlines():
            match = INCLUDE_RE.match(line)
            if match:
                visit(path.parent / match.group(1))

    visit(style_root / entrypoint)
    return codes


def parse_typ_codes(path: Path) -> dict[str, set[tuple[int, int]]]:
    """Parse point/line/polygon definitions from the cp1251 TYP source."""
    text = path.read_bytes().decode("cp1251")
    result: dict[str, set[tuple[int, int]]] = defaultdict(set)
    section: str | None = None
    type_id: int | None = None
    subtype: int | None = None

    def flush() -> None:
        nonlocal type_id, subtype
        if section is not None and type_id is not None:
            raw_subtype = 0 if subtype is None else subtype
            # Accept historical combined Type=0x1341f syntax too, so the audit
            # can identify semantic coverage even in an old source revision.
            if subtype is None and type_id > 0xFFF:
                normalized = (type_id >> 8, type_id & 0xFF)
            else:
                normalized = (type_id, raw_subtype)
            result[section].add(normalized)
        type_id = None
        subtype = None

    for line in text.splitlines():
        match = SECTION_RE.match(line)
        if match:
            flush()
            section = match.group(1).lower()
            continue
        if END_RE.match(line):
            flush()
            section = None
            continue
        if section is None:
            continue
        field = FIELD_RE.match(line)
        if not field:
            continue
        value = int(field.group(2), 16)
        if field.group(1).lower() == "type":
            type_id = value
        else:
            subtype = value
    flush()
    return dict(result)


def audit(repo_root: Path) -> int:
    style_root = repo_root / "styles" / "uralla"
    typ_path = repo_root / "styles" / "uralla.txt"
    typ_codes = parse_typ_codes(typ_path)

    failed = False
    for kind, entrypoint in STYLE_ENTRYPOINTS.items():
        style_codes = collect_style_codes(style_root, entrypoint)
        defined = typ_codes.get(kind, set())
        missing = sorted(style_codes - defined)
        missing_custom = [code for code in missing if is_extended_custom(code)]
        native_without_override = [code for code in missing if not is_extended_custom(code)]
        unused = sorted(defined - style_codes)

        print(f"{kind}: style={len(style_codes)} typ={len(defined)}")
        if missing_custom:
            failed = True
            print("  ERROR custom style type without TYP definition:")
            for code in missing_custom:
                print(f"    {format_code(code)}")
        if native_without_override:
            print("  native style type without custom TYP override:")
            for code in native_without_override:
                print(f"    {format_code(code)}")
        if unused:
            print("  TYP definition without active style use:")
            for code in unused:
                print(f"    {format_code(code)}")

    return 1 if failed else 0


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    return audit(repo_root)


if __name__ == "__main__":
    sys.exit(main())

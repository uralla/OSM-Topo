#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / "styles" / "uralla" / "lines"
TYP = ROOT / "styles" / "uralla.txt"
PRE_MIGRATION_COMMIT = "6526c6f29dcb9a298db711d97dbbcda725f6ea69"


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        raw.decode("cp1251")
        return "cp1251"


def section_pattern(kind: str) -> re.Pattern[str]:
    return re.compile(rf"(?ims)^\[{re.escape(kind)}\][ \t]*\r?\n.*?^\[end\][ \t]*(?:\r?\n)?")


def typed_sections(text: str, kind: str, type_code: str) -> list[re.Match[str]]:
    tr = re.compile(rf"(?im)^Type={re.escape(type_code)}(?:\b|$)")
    return [m for m in section_pattern(kind).finditer(text) if tr.search(m.group(0))]


def one(text: str, kind: str, type_code: str) -> str:
    m = typed_sections(text, kind, type_code)
    if len(m) != 1:
        raise RuntimeError(f"{kind} {type_code}: expected 1 section, got {len(m)}")
    return m[0].group(0)


def patch_lines() -> None:
    s = LINES.read_text(encoding="utf-8")
    old = (
        "railway=rail & service=* & length()>500 [0x10f1b resolution 23-23 continue]\n"
        "railway=rail & service=* [0x10f1b resolution 24]"
    )
    new = (
        "railway=rail & service=* & length()>500 [0x10f1f resolution 23-23 continue]\n"
        "railway=rail & service=* [0x10f1f resolution 24]"
    )
    if old in s:
        s = s.replace(old, new, 1)
    elif new not in s:
        raise RuntimeError("service railway rule block not found")
    LINES.write_text(s, encoding="utf-8", newline="")


def patch_typ() -> None:
    raw = TYP.read_bytes()
    enc = detect_encoding(raw)
    s = raw.decode(enc)

    # Protect already accepted/current definitions from this repair.
    protected = {
        ("_line", "0x10f07"): one(s, "_line", "0x10f07"),
        ("_polygon", "0x10f11"): one(s, "_polygon", "0x10f11"),
        ("_line", "0x10e04"): one(s, "_line", "0x10e04"),
        ("_line", "0x10f1a"): one(s, "_line", "0x10f1a"),
    }

    if typed_sections(s, "_line", "0x10f1f"):
        raise RuntimeError("0x10f1f is unexpectedly already occupied")

    # Current 0x10f1b is the service-rail graphic produced by the previous migration.
    current = typed_sections(s, "_line", "0x10f1b")
    if len(current) != 1:
        raise RuntimeError(f"current 0x10f1b count={len(current)}")
    m = current[0]
    service_block = re.sub(r"(?im)^Type=0x10f1b(?:\b|$)", "Type=0x10f1f", m.group(0), count=1)
    s = s[:m.start()] + service_block + s[m.end():]

    # Recover the exact marina section from the authoritative source immediately
    # before the collision migration; do not redraw/recreate it by hand.
    old_raw = subprocess.check_output(
        ["git", "show", f"{PRE_MIGRATION_COMMIT}:styles/uralla.txt"]
    )
    old_enc = detect_encoding(old_raw)
    old_text = old_raw.decode(old_enc)
    marina = one(old_text, "_line", "0x10f1b")
    if "marina" not in marina.lower():
        raise RuntimeError("historical 0x10f1b is not the marina section")

    # Insert marina immediately before the next neighboring custom-line section.
    next_sections = typed_sections(s, "_line", "0x10f1c")
    if len(next_sections) != 1:
        raise RuntimeError("0x10f1c insertion anchor missing")
    pos = next_sections[0].start()
    s = s[:pos] + marina + s[pos:]

    if len(typed_sections(s, "_line", "0x10f1b")) != 1:
        raise RuntimeError("marina 0x10f1b not restored uniquely")
    if len(typed_sections(s, "_line", "0x10f1f")) != 1:
        raise RuntimeError("service railway 0x10f1f not created uniquely")
    if "marina" not in one(s, "_line", "0x10f1b").lower():
        raise RuntimeError("0x10f1b does not contain marina after repair")

    for key, before in protected.items():
        if one(s, *key) != before:
            raise RuntimeError(f"protected TYP section changed: {key}")

    TYP.write_bytes(s.encode(enc))
    print(f"Restored marina 0x10f1b; moved service railway to 0x10f1f; encoding={enc}")


def main() -> None:
    patch_lines()
    patch_typ()


if __name__ == "__main__":
    main()

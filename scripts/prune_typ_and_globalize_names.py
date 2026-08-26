#!/usr/bin/env python3
"""One-shot migration: globalize name abbreviations and prune unused TYP graphics.

The final repository keeps styles/uralla.txt as the direct authoritative TYP
source.  This helper is deleted by its companion workflow after a successful
validated commit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla"
TYP = ROOT / "styles" / "uralla.txt"
LINES = STYLE / "lines"
POLYGONS = STYLE / "polygons"
NAME = STYLE / "inc" / "name"

TYPE_RE = re.compile(r"\[\s*(0x[0-9a-fA-F]+)\b")
INCLUDE_RE = re.compile(r"^\s*include\s+'([^']+)'\s*;", re.MULTILINE)
GRAPHIC_SECTION_RE = re.compile(
    r"(?ims)^\[(?P<kind>_point|_line|_polygon)\]\s*\r?\n.*?^\[end\]\s*(?:\r?\n)?"
)
DRAW_ORDER_RE = re.compile(r"(?ims)^\[_drawOrder\]\s*\r?\n.*?^\[end\]\s*(?:\r?\n)?")


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        raw.decode("cp1251")
        return "cp1251"


def active_source(text: str) -> str:
    """Remove mkgmap comment text while preserving active rule continuations."""
    out: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        # Current style uses # only for comments, not inside active string values.
        out.append(line.split("#", 1)[0])
    return "\n".join(out)


def include_closure(entry: Path) -> list[Path]:
    """Follow only includes reachable from one production style entry file."""
    seen: set[Path] = set()
    ordered: list[Path] = []

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        if not path.is_file():
            raise RuntimeError(f"style include not found: {path}")
        seen.add(path)
        ordered.append(path)
        active = active_source(path.read_text(encoding="utf-8"))
        for rel in INCLUDE_RE.findall(active):
            visit(STYLE / rel)

    visit(entry)
    return ordered


def used_types(entry: Path) -> set[int]:
    used: set[int] = set()
    for path in include_closure(entry):
        active = active_source(path.read_text(encoding="utf-8"))
        used.update(int(code, 16) for code in TYPE_RE.findall(active))
    return used


def patch_global_names() -> None:
    lines = LINES.read_text(encoding="utf-8")

    old_block = """# сокращаем статусные части названий улиц (пока отлючено)
 name=* { name '${name|subst:улица=> ул.
\t\t     |subst:переулок=> пер.
\t\t\t |subst:проспект=> пр-т
\t\t     |subst:проезд=> пр-д
\t\t\t |subst:разъезд=> раз.
\t\t     |subst:тракт=> тр-т
\t\t     |subst:площадь=> пл.
\t\t     |subst:имени=> им.
\t\t     |subst:бульвар=> бл-р
\t\t     |subst:шоссе=> ш.
\t\t     |subst:дорога=> дор.
\t\t     |subst:тупик=> туп.
\t\t     |subst:микрорайон=> мкр.
\t\t     |subst:аллея=> алл.
\t\t     |subst:линия=> лин.
\t\t     |subst:набережная=> наб.
\t\t\t |subst:Восточный=> Вост.
\t\t\t |subst:Западный=> Зап.
\t\t\t |subst:Южный=> Юж.
\t\t\t |subst:Северный=> Сев.
\t\t\t |subst:имени=> им.
\t\t\t}' }

"""
    if old_block not in lines:
        raise RuntimeError("legacy line-only abbreviation block not found")
    lines = lines.replace(old_block, "", 1)
    anchor = "include 'inc/contour_lines';"
    if "include 'inc/name';" not in lines:
        if anchor not in lines:
            raise RuntimeError("line include anchor not found")
        lines = lines.replace(anchor, "include 'inc/name';\n" + anchor, 1)
    LINES.write_text(lines, encoding="utf-8", newline="")

    polygons = POLYGONS.read_text(encoding="utf-8")
    if "include 'inc/name';" not in polygons:
        anchor = "addr:housenumber=* {set mkgmap:execute_finalize_rules=true}\n"
        if anchor not in polygons:
            raise RuntimeError("polygon name include anchor not found")
        polygons = polygons.replace(anchor, anchor + "include 'inc/name';\n", 1)
    POLYGONS.write_text(polygons, encoding="utf-8", newline="")

    name = NAME.read_text(encoding="utf-8")
    old = """# Короткие подписи POI/объектов: иконка уже передаёт тип, но статусную часть имени сохраняем.
name=* { set name='${name|subst:Беседка=>Бес.|subst:беседка=>бес.}' }
"""
    new = """# [CUSTOM/АВТОРСКОЕ] Global compact labels for points, lines and polygons.
# This include is intentionally used by all three production style entry files.
name=* { set name='${name|subst:улица=> ул.
                     |subst:переулок=> пер.
                     |subst:проспект=> пр-т
                     |subst:проезд=> пр-д
                     |subst:разъезд=> раз.
                     |subst:тракт=> тр-т
                     |subst:площадь=> пл.
                     |subst:имени=> им.
                     |subst:бульвар=> бл-р
                     |subst:шоссе=> ш.
                     |subst:дорога=> дор.
                     |subst:тупик=> туп.
                     |subst:микрорайон=> мкр.
                     |subst:аллея=> алл.
                     |subst:линия=> лин.
                     |subst:набережная=> наб.
                     |subst:Восточный=> Вост.
                     |subst:Западный=> Зап.
                     |subst:Южный=> Юж.
                     |subst:Северный=> Сев.
                     |subst:Беседка=>Бес.
                     |subst:беседка=>бес.}' }
"""
    if old not in name:
        raise RuntimeError("existing gazebo abbreviation rule not found")
    NAME.write_text(name.replace(old, new, 1), encoding="utf-8", newline="")


def point_code(section: str) -> int:
    tm = re.search(r"(?im)^Type\s*=\s*0x([0-9a-f]+)\b", section)
    if not tm:
        raise RuntimeError("TYP point section without Type")
    type_value = int(tm.group(1), 16)
    sm = re.search(r"(?im)^SubType\s*=\s*0x([0-9a-f]+)\b", section)
    if sm:
        return (type_value << 8) | int(sm.group(1), 16)
    return type_value


def simple_code(section: str) -> int:
    tm = re.search(r"(?im)^Type\s*=\s*0x([0-9a-f]+)\b", section)
    if not tm:
        raise RuntimeError("TYP graphic section without Type")
    return int(tm.group(1), 16)


def section_label(section: str) -> str:
    for pattern in (
        r"(?im)^String1\s*=\s*[^,]*,(.*)$",
        r"(?im)^String2\s*=\s*[^,]*,(.*)$",
        r"(?im)^;GRMN_TYPE:\s*(.*)$",
    ):
        m = re.search(pattern, section)
        if m:
            return m.group(1).strip()[:80]
    return ""


def prune_draw_order(text: str, used_polygons: set[int]) -> tuple[str, int]:
    matches = list(DRAW_ORDER_RE.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"expected one _drawOrder section, found {len(matches)}")
    m = matches[0]
    block = m.group(0)
    kept: list[str] = []
    removed = 0
    for line in block.splitlines(keepends=True):
        tm = re.match(r"(?i)^\s*Type\s*=\s*0x([0-9a-f]+)\s*,", line)
        if tm and int(tm.group(1), 16) not in used_polygons:
            removed += 1
            continue
        kept.append(line)
    return text[: m.start()] + "".join(kept) + text[m.end() :], removed


def prune_typ() -> None:
    used = {
        "_point": used_types(STYLE / "points"),
        "_line": used_types(STYLE / "lines"),
        "_polygon": used_types(STYLE / "polygons"),
    }

    print("Production include closures:")
    for entry in ("points", "lines", "polygons"):
        closure = include_closure(STYLE / entry)
        print(f"  {entry}: " + ", ".join(str(p.relative_to(STYLE)) for p in closure))
    print("Referenced Garmin type counts:", {k: len(v) for k, v in used.items()})

    raw = TYP.read_bytes()
    enc = detect_encoding(raw)
    text = raw.decode(enc)
    before_bytes = len(raw)

    removed: dict[str, list[tuple[int, str]]] = {k: [] for k in used}
    before_counts = {k: 0 for k in used}
    after_counts = {k: 0 for k in used}

    sections = list(GRAPHIC_SECTION_RE.finditer(text))
    for m in sections:
        before_counts[m.group("kind").lower()] += 1

    for m in reversed(sections):
        kind = m.group("kind").lower()
        section = m.group(0)
        code = point_code(section) if kind == "_point" else simple_code(section)
        if code in used[kind]:
            continue
        removed[kind].append((code, section_label(section)))
        text = text[: m.start()] + text[m.end() :]

    text, draw_removed = prune_draw_order(text, used["_polygon"])

    # Remove blank-line archaeology left by deleted graphic blocks without touching
    # TYP syntax or comments that remain relevant to retained sections.
    text = re.sub(r"(?:\r?\n){4,}", "\n\n\n", text)

    for m in GRAPHIC_SECTION_RE.finditer(text):
        after_counts[m.group("kind").lower()] += 1

    # Strong postcondition: every retained graphic entry is referenced by the
    # production style include graph in the matching Garmin object namespace.
    orphans: list[str] = []
    for m in GRAPHIC_SECTION_RE.finditer(text):
        kind = m.group("kind").lower()
        section = m.group(0)
        code = point_code(section) if kind == "_point" else simple_code(section)
        if code not in used[kind]:
            orphans.append(f"{kind} 0x{code:x} {section_label(section)}")
    if orphans:
        raise RuntimeError("retained unused TYP sections: " + "; ".join(orphans[:20]))

    TYP.write_bytes(text.encode(enc))
    after_bytes = TYP.stat().st_size

    print(f"TYP encoding preserved: {enc}")
    print(f"TYP size: {before_bytes} -> {after_bytes} bytes ({before_bytes - after_bytes} removed)")
    print("Graphic sections before:", before_counts)
    print("Graphic sections after: ", after_counts)
    print(f"Removed _drawOrder entries: {draw_removed}")
    for kind in ("_point", "_line", "_polygon"):
        items = sorted(removed[kind])
        print(f"Removed {kind}: {len(items)}")
        for code, label in items:
            print(f"  0x{code:x}  {label}")

    ozon_hits = [
        (kind, code, label)
        for kind, items in removed.items()
        for code, label in items
        if "ozon" in label.casefold() or "озон" in label.casefold()
    ]
    print("Removed Ozon-labelled entries:", ozon_hits or "none labelled explicitly")


def main() -> None:
    patch_global_names()
    prune_typ()
    print("Global name migration and strict TYP pruning completed")


if __name__ == "__main__":
    main()

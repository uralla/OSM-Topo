from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla"
TYP = ROOT / "styles" / "uralla.txt"
TYPE_RE = re.compile(r"\[\s*(0x[0-9a-fA-F]+)\b")
INCLUDE_RE = re.compile(r"^\s*include\s+'([^']+)'\s*;", re.MULTILINE)
SECTION_RE = re.compile(
    r"(?ims)^\[(?P<kind>_point|_line|_polygon)\]\s*\r?\n.*?^\[end\]\s*(?:\r?\n)?"
)
DRAW_RE = re.compile(r"(?ims)^\[_drawOrder\]\s*\r?\n.*?^\[end\]\s*(?:\r?\n)?")


def active_source(text: str) -> str:
    result = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        result.append(line.split("#", 1)[0])
    return "\n".join(result)


def closure(entry: Path) -> list[Path]:
    result = []
    seen = set()

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        if not path.is_file():
            raise AssertionError(f"missing style include: {path}")
        seen.add(path)
        result.append(path)
        active = active_source(path.read_text(encoding="utf-8"))
        for rel in INCLUDE_RE.findall(active):
            visit(STYLE / rel)

    visit(entry)
    return result


def used(entry: str) -> set[int]:
    result = set()
    for path in closure(STYLE / entry):
        active = active_source(path.read_text(encoding="utf-8"))
        result.update(int(value, 16) for value in TYPE_RE.findall(active))
    return result


def typ_text() -> str:
    raw = TYP.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251")


def section_code(kind: str, section: str) -> int:
    tm = re.search(r"(?im)^Type\s*=\s*0x([0-9a-f]+)\b", section)
    assert tm is not None
    value = int(tm.group(1), 16)
    if kind == "_point":
        sm = re.search(r"(?im)^SubType\s*=\s*0x([0-9a-f]+)\b", section)
        if sm:
            value = (value << 8) | int(sm.group(1), 16)
    return value


class TypUsageTests(unittest.TestCase):
    def test_global_name_rules_are_shared_by_all_object_kinds(self) -> None:
        for entry in ("points", "lines", "polygons"):
            text = (STYLE / entry).read_text(encoding="utf-8")
            self.assertIn("include 'inc/name';", text, entry)
        lines = (STYLE / "lines").read_text(encoding="utf-8")
        self.assertNotIn("сокращаем статусные части названий улиц", lines)
        name = (STYLE / "inc" / "name").read_text(encoding="utf-8")
        for fragment in (
            "subst:улица=> ул.",
            "subst:переулок=> пер.",
            "subst:проспект=> пр-т",
            "subst:Беседка=>Бес.",
            "subst:беседка=>бес.",
        ):
            self.assertIn(fragment, name)

    def test_every_include_file_is_reachable_from_production_style(self) -> None:
        reachable = set()
        for entry in ("points", "lines", "polygons"):
            reachable.update(closure(STYLE / entry))
        actual = {path.resolve() for path in (STYLE / "inc").iterdir() if path.is_file()}
        unreachable = sorted(str(path.relative_to(ROOT)) for path in actual - reachable)
        self.assertEqual([], unreachable)

    def test_typ_has_no_graphic_sections_unused_by_production_style(self) -> None:
        expected = {
            "_point": used("points"),
            "_line": used("lines"),
            "_polygon": used("polygons"),
        }
        leftovers = []
        for match in SECTION_RE.finditer(typ_text()):
            kind = match.group("kind").lower()
            code = section_code(kind, match.group(0))
            if code not in expected[kind]:
                leftovers.append(f"{kind}:0x{code:x}")
        self.assertEqual([], leftovers)

    def test_typ_has_no_duplicate_graphic_sections(self) -> None:
        seen = set()
        duplicates = []
        for match in SECTION_RE.finditer(typ_text()):
            kind = match.group("kind").lower()
            code = section_code(kind, match.group(0))
            key = (kind, code)
            if key in seen:
                duplicates.append(f"{kind}:0x{code:x}")
            seen.add(key)
        self.assertEqual([], duplicates)

    def test_draw_order_contains_only_used_polygon_types(self) -> None:
        text = typ_text()
        matches = list(DRAW_RE.finditer(text))
        self.assertEqual(1, len(matches))
        used_polygons = used("polygons")
        leftovers = []
        for line in matches[0].group(0).splitlines():
            tm = re.match(r"(?i)^\s*Type\s*=\s*0x([0-9a-f]+)\s*,", line)
            if tm and int(tm.group(1), 16) not in used_polygons:
                leftovers.append(line)
        self.assertEqual([], leftovers)

    def test_every_used_polygon_type_has_draw_order(self) -> None:
        text = typ_text()
        matches = list(DRAW_RE.finditer(text))
        self.assertEqual(1, len(matches))
        drawn = {
            int(match.group(1), 16)
            for line in matches[0].group(0).splitlines()
            if (match := re.match(r"(?i)^\s*Type\s*=\s*0x([0-9a-f]+)\s*,", line))
        }
        self.assertEqual([], sorted(used("polygons") - drawn))


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla"
TYP = ROOT / "styles" / "uralla.txt"
INCLUDE_RE = re.compile(r"^\s*include\s+'([^']+)'\s*;", re.MULTILINE)
STYLE_115_RE = re.compile(r"\[0x115([0-9a-fA-F]{2})\b")
TYP_115_RE = re.compile(
    r"(?ms)^\[_point\]\s*\nType=0x115\s*\nSubType=0x([0-9a-fA-F]{2})\b.*?^\[end\]"
)

# Authoritative current remainder for POI-01. Shrink this set as each symbol is
# moved out of group 0x115; when migration is complete it must become empty.
REMAINING_115 = {0x00, 0x01, 0x04, 0x06, 0x07, 0x09}


def _production_point_files() -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        seen.add(path)
        result.append(path)
        text = path.read_text(encoding="utf-8")
        for relative in INCLUDE_RE.findall(text):
            visit(STYLE / relative)

    visit(STYLE / "points")
    return result


class Group115MigrationTests(unittest.TestCase):
    def test_style_has_only_the_known_remaining_115_subtypes(self) -> None:
        found: set[int] = set()
        for path in _production_point_files():
            text = path.read_text(encoding="utf-8")
            found.update(int(value, 16) for value in STYLE_115_RE.findall(text))
        self.assertEqual(REMAINING_115, found)

    def test_typ_has_exactly_the_same_remaining_115_subtypes(self) -> None:
        typ = TYP.read_text(encoding="utf-8")
        found = {int(value, 16) for value in TYP_115_RE.findall(typ)}
        self.assertEqual(REMAINING_115, found)

    def test_already_migrated_115_types_have_no_current_tail(self) -> None:
        production = "\n".join(
            path.read_text(encoding="utf-8") for path in _production_point_files()
        )
        typ = TYP.read_text(encoding="utf-8")
        for old_code, subtype in (("0x11505", "05"), ("0x1150a", "0a")):
            self.assertNotIn(old_code, production)
            self.assertNotRegex(
                typ,
                rf"(?ms)^\[_point\]\s*\nType=0x115\s*\nSubType=0x{subtype}\b.*?^\[end\]",
            )


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"

SECTION_RE = re.compile(r"(?ims)^\[(_point|_line|_polygon)\]\s*\n.*?^\[end\]\s*(?:\n|$)")
XPM_RE = re.compile(r'(?im)^Xpm="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"')
BORDER_RE = re.compile(r"(?im)^BorderWidth\s*=\s*(\d+)\s*$")


def typ_text() -> str:
    raw = TYP.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251")


class TypNightModeTests(unittest.TestCase):
    def test_direct_typ_has_no_explicit_night_only_fields(self) -> None:
        text = typ_text()
        self.assertIsNone(re.search(r"(?im)^\s*NightXpm\s*=", text))
        self.assertIsNone(re.search(r"(?im)^\s*NightcustomColor\s*[:=]", text))
        self.assertIsNone(
            re.search(r"(?im)^\s*CustomColor\s*=\s*DayAndNight\s*$", text)
        )

    def test_line_xpm_palettes_have_no_implicit_night_alternatives(self) -> None:
        text = typ_text()
        problems: list[str] = []
        for section in SECTION_RE.finditer(text):
            if section.group(1) != "_line":
                continue
            block = section.group(0)
            hm = XPM_RE.search(block)
            if not hm:
                continue
            _width, height, colors, _cpp = map(int, hm.groups())
            tm = re.search(r"(?im)^Type=(0x[0-9a-f]+)\b", block)
            typ = tm.group(1) if tm else "?"
            bm = BORDER_RE.search(block)
            border = int(bm.group(1)) if bm else 0

            if height > 0 and colors > 2:
                problems.append(f"{typ}: bitmap has {colors} colours")
            elif height == 0 and border > 0 and colors > 2:
                problems.append(f"{typ}: bordered solid line has {colors} colours")
            elif height == 0 and border == 0 and colors > 1:
                problems.append(f"{typ}: unbordered solid line has {colors} colours")

        self.assertEqual([], problems)


if __name__ == "__main__":
    unittest.main()

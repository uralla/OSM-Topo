from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
TYP = REPO_ROOT / "styles" / "uralla.txt"
WATER_POINTS = REPO_ROOT / "styles" / "uralla" / "inc" / "water_points"


def _point_section(text: str, type_code: str) -> str:
    for match in re.finditer(r"\[_point\]\n(.*?)\n\[end\]", text, re.S | re.I):
        section = match.group(1)
        if re.search(rf"^Type={re.escape(type_code)}$", section, re.M | re.I):
            return section
    raise AssertionError(f"point type {type_code} not found")


class WaterSourceTypTests(unittest.TestCase):
    def test_water_source_icons_have_no_persistent_map_label(self) -> None:
        text = TYP.read_text(encoding="cp1251")
        for type_code in ("0x6511", "0x6512"):
            section = _point_section(text, type_code)
            self.assertRegex(section, r"(?mi)^FontStyle=NoLabel$")

    def test_style_keeps_only_information_labels(self) -> None:
        text = WATER_POINTS.read_text(encoding="utf-8")
        self.assertNotIn("addlabel 'вода'", text)
        self.assertNotIn("addlabel 'вода (пересых.)'", text)
        self.assertIn("name '${name} (пересых.)' | 'пересых. источник'", text)


if __name__ == "__main__":
    unittest.main()

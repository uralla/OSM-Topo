from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
TYP = REPO_ROOT / "styles" / "uralla.txt"
WATER_POINTS = REPO_ROOT / "styles" / "uralla" / "inc" / "water_points"


def _point_section(text: str, type_code: str, subtype_code: str) -> str:
    for match in re.finditer(r"\[_point\]\n(.*?)\n\[end\]", text, re.S | re.I):
        section = match.group(1)
        if not re.search(rf"^Type={re.escape(type_code)}$", section, re.M | re.I):
            continue
        if re.search(rf"^SubType={re.escape(subtype_code)}$", section, re.M | re.I):
            return section
    raise AssertionError(f"point type {type_code}/{subtype_code} not found")


class WaterSourceTypTests(unittest.TestCase):
    def test_water_source_icons_have_no_persistent_map_label(self) -> None:
        text = TYP.read_text(encoding="utf-8")
        for subtype_code in ("0x11", "0x12"):
            section = _point_section(text, "0x065", subtype_code)
            self.assertRegex(section, r"(?mi)^FontStyle=NoLabel(?: \(invisible\))?$")

    def test_style_keeps_only_information_labels(self) -> None:
        text = WATER_POINTS.read_text(encoding="utf-8")
        self.assertNotIn("addlabel 'вода'", text)
        self.assertNotIn("addlabel 'вода (пересых.)'", text)
        self.assertIn(
            "name '${name|subst: (сезонный)=>|subst: (Сезонный)=>} (пересых.)' | 'пересых. источник'",
            text,
        )


if __name__ == "__main__":
    unittest.main()

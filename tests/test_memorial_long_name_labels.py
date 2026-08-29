from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIORITY_POINTS = ROOT / "styles" / "uralla" / "inc" / "priority_points"


class MemorialLongNameLabelsTests(unittest.TestCase):
    def test_explicit_memorial_subtypes_get_short_long_name_labels(self) -> None:
        text = PRIORITY_POINTS.read_text(encoding="utf-8")
        expected = {
            "plaque": "памятная табличка",
            "stele": "стела",
            "stone": "памятный камень",
            "statue": "памятник",
            "obelisk": "обелиск",
            "bust": "бюст",
            "sculpture": "скульптура",
            "cross": "памятный крест",
        }
        generic = "historic=memorial { name '${name}' | '${inscription}' } [0x6403 resolution 24]"
        generic_index = text.index(generic)
        for subtype, label in expected.items():
            rule = (
                f"historic=memorial & memorial={subtype} & uralla:long_name=yes "
                f"{{ name '{label}' }} [0x6403 resolution 24]"
            )
            self.assertIn(rule, text)
            self.assertLess(text.index(rule), generic_index)

    def test_unapproved_broad_memorial_fallbacks_are_absent(self) -> None:
        text = PRIORITY_POINTS.read_text(encoding="utf-8")
        self.assertNotIn("memorial=war_memorial & uralla:long_name=yes", text)
        self.assertNotIn("historic=memorial & uralla:long_name=yes { name 'памятник' }", text)


if __name__ == "__main__":
    unittest.main()

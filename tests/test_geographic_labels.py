from __future__ import annotations

from pathlib import Path
import unittest

from uralla_build.preprocessor import enrich_geographic_label_tags


ROOT = Path(__file__).resolve().parents[1]
NAME_INCLUDE = ROOT / "styles" / "uralla" / "inc" / "name"


class GeographicDisplayLabelTests(unittest.TestCase):
    def assert_label(self, tags: dict[str, str], expected: str) -> None:
        result, changed = enrich_geographic_label_tags(tags)
        self.assertTrue(changed)
        self.assertEqual(result["uralla:label"], expected)
        self.assertEqual(result["name"], tags["name"])

    def assert_unchanged(self, tags: dict[str, str]) -> None:
        result, changed = enrich_geographic_label_tags(tags)
        self.assertFalse(changed)
        self.assertEqual(result, tags)

    def test_peak_and_volcano_strip_only_leading_type_token(self) -> None:
        for name in ("Гора Иремель", "гора Иремель", "Г. Иремель", "г Иремель", "г.Иремель"):
            with self.subTest(name=name):
                self.assert_label({"natural": "peak", "name": name}, "Иремель")

        self.assert_label({"natural": "volcano", "name": "гора Эльбрус"}, "Эльбрус")
        self.assert_unchanged({"natural": "peak", "name": "Большая Гора"})
        self.assert_unchanged({"natural": "peak", "name": "Белая Гора"})

    def test_ridge_strips_leading_type_token(self) -> None:
        for name in ("Хребет Нурали", "хребет Нурали", "хр. Нурали", "хр Нурали"):
            with self.subTest(name=name):
                self.assert_label({"natural": "ridge", "name": name}, "Нурали")

        self.assert_unchanged({"natural": "ridge", "name": "Каменный Хребет"})

    def test_lake_requires_lake_semantics(self) -> None:
        for name in ("Озеро Белое", "озеро Белое", "Оз. Белое", "оз Белое"):
            with self.subTest(name=name):
                self.assert_label(
                    {"natural": "water", "water": "lake", "name": name},
                    "Белое",
                )

        self.assert_label({"natural": "lake", "name": "Оз. Тургояк"}, "Тургояк")
        self.assert_unchanged({"natural": "water", "name": "Оз. Белое"})
        self.assert_unchanged(
            {"natural": "water", "water": "reservoir", "name": "Оз. Белое"}
        )
        self.assert_unchanged(
            {"natural": "water", "water": "lake", "name": "Черное Озеро"}
        )

    def test_waterfall_variants_are_supported(self) -> None:
        for name in (
            "Водопад Кивач",
            "водопад Кивач",
            "вод. Кивач",
            "вод Кивач",
            "вдп. Кивач",
            "вдп Кивач",
        ):
            with self.subTest(name=name):
                self.assert_label({"natural": "waterfall", "name": name}, "Кивач")

    def test_type_word_is_not_stripped_from_unrelated_objects(self) -> None:
        self.assert_unchanged({"place": "village", "name": "Гора Иремель"})
        self.assert_unchanged({"highway": "residential", "name": "Озеро Белое"})

    def test_style_prefers_render_only_label_before_global_name_compacting(self) -> None:
        text = NAME_INCLUDE.read_text(encoding="utf-8")
        label_rule = "uralla:label=* { set name='${uralla:label}' }"
        global_rule = "name=* { set name='${name|subst:Великая Отечественная война=>ВОВ"
        self.assertIn(label_rule, text)
        self.assertIn(global_rule, text)
        self.assertLess(text.index(label_rule), text.index(global_rule))


if __name__ == "__main__":
    unittest.main()

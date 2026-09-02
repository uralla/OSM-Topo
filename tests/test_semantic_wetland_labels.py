from __future__ import annotations

import unittest

from uralla_build.preprocessor import enrich_geographic_label_tags


class SemanticWetlandLabelTests(unittest.TestCase):
    def test_single_word_wetland_names_are_not_abbreviated(self) -> None:
        cases = {
            "Верхнее болото": "Верхнее",
            "Нижнее болото": "Нижнее",
            "Большое болото": "Большое",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                tags, changed = enrich_geographic_label_tags(
                    {"natural": "wetland", "wetland": "swamp", "name": name}
                )
                self.assertTrue(changed)
                self.assertEqual(tags["uralla:label"], expected)

    def test_multiword_size_wetland_name_is_compacted(self) -> None:
        tags, changed = enrich_geographic_label_tags(
            {
                "natural": "wetland",
                "wetland": "marsh",
                "name": "Большое Клюквенное болото",
            }
        )
        self.assertTrue(changed)
        self.assertEqual(tags["uralla:label"], "Бол. Клюквенное")

    def test_leading_generic_wetland_type_is_removed(self) -> None:
        tags, changed = enrich_geographic_label_tags(
            {"natural": "wetland", "name": "Болото Клюквенное"}
        )
        self.assertTrue(changed)
        self.assertEqual(tags["uralla:label"], "Клюквенное")

    def test_capitalized_wetland_suffix_is_preserved(self) -> None:
        tags, changed = enrich_geographic_label_tags(
            {"natural": "wetland", "name": "Чёрное Болото"}
        )
        self.assertFalse(changed)
        self.assertNotIn("uralla:label", tags)


if __name__ == "__main__":
    unittest.main()

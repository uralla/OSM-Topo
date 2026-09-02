from __future__ import annotations

import unittest

from uralla_build.preprocessor import enrich_geographic_label_tags
from uralla_build.semantic_apply import _respect_lake_suffix_capitalization


class SemanticLakeLabelTests(unittest.TestCase):
    def test_single_word_directional_lake_names_are_not_abbreviated(self) -> None:
        cases = {
            "Верхнее озеро": "Верхнее",
            "Нижнее озеро": "Нижнее",
            "Большое озеро": "Большое",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                tags, changed = enrich_geographic_label_tags(
                    {"water": "lake", "name": name}
                )
                self.assertTrue(changed)
                self.assertEqual(tags["uralla:label"], expected)

    def test_multiword_size_lake_name_is_still_compacted(self) -> None:
        tags, changed = enrich_geographic_label_tags(
            {"water": "lake", "name": "Большое Катасьминское озеро"}
        )
        self.assertTrue(changed)
        self.assertEqual(tags["uralla:label"], "Бол. Катасьминское")

    def test_lowercase_type_suffix_is_removed(self) -> None:
        tags = _respect_lake_suffix_capitalization(
            {"water": "lake", "name": "Чёрное озеро"}
        )
        self.assertEqual(tags["uralla:label"], "Чёрное")

    def test_capitalized_suffix_is_preserved_as_name_text(self) -> None:
        tags = _respect_lake_suffix_capitalization(
            {"water": "lake", "name": "Чёрное Озеро"}
        )
        self.assertNotIn("uralla:label", tags)

    def test_capitalized_suffix_is_restored_after_size_compaction(self) -> None:
        tags = _respect_lake_suffix_capitalization(
            {
                "water": "lake",
                "name": "Большое Катасьминское Озеро",
                "uralla:label": "Бол. Катасьминское",
            }
        )
        self.assertEqual(tags["uralla:label"], "Бол. Катасьминское Озеро")

    def test_lowercase_suffix_stays_removed_after_size_compaction(self) -> None:
        tags = _respect_lake_suffix_capitalization(
            {
                "water": "lake",
                "name": "Большое Катасьминское озеро",
                "uralla:label": "Бол. Катасьминское",
            }
        )
        self.assertEqual(tags["uralla:label"], "Бол. Катасьминское")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from uralla_build.semantic_apply import _respect_lake_suffix_capitalization


class SemanticLakeLabelTests(unittest.TestCase):
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

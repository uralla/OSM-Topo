from __future__ import annotations

import unittest

from uralla_build.long_names_audit import (
    AuditState,
    _term_rows,
    add_name_to_state,
    length_bucket,
    normalize_words,
    primary_tag,
    significant_words,
)


class LongNamesAuditTests(unittest.TestCase):
    def test_normalize_words_handles_case_punctuation_and_yo(self) -> None:
        self.assertEqual(
            normalize_words("Ёлочная улица — имени Героя"),
            ["елочная", "улица", "имени", "героя"],
        )

    def test_significant_words_drop_common_stopwords(self) -> None:
        self.assertEqual(
            significant_words("Тропа в лесу и по берегу"),
            ["тропа", "лесу", "берегу"],
        )

    def test_length_buckets(self) -> None:
        self.assertEqual(length_bucket(31), "31-40")
        self.assertEqual(length_bucket(50), "41-50")
        self.assertEqual(length_bucket(75), "51-75")
        self.assertEqual(length_bucket(100), "76-100")
        self.assertEqual(length_bucket(101), ">100")

    def test_primary_tag_uses_stable_priority(self) -> None:
        self.assertEqual(
            primary_tag({"name": "X", "natural": "wood", "highway": "path"}),
            "highway=path",
        )
        self.assertEqual(primary_tag({"name": "X"}), "other")

    def test_long_name_updates_object_tag_and_term_statistics(self) -> None:
        state = AuditState()
        name = "Экологическая тропа имени выдающегося местного исследователя"
        added = add_name_to_state(
            state,
            name=name,
            tags={"highway": "path", "name": name},
            kind="way",
            geometry="open_way",
            object_id=42,
            limit=30,
            example_limit=3,
        )
        self.assertTrue(added)
        self.assertEqual(state.long_names, 1)
        self.assertEqual(state.by_kind["way"], 1)
        self.assertEqual(state.by_geometry["open_way"], 1)
        self.assertEqual(state.by_primary_tag["highway=path"], 1)
        self.assertEqual(state.linear_by_tag["highway=path"], 1)
        self.assertEqual(state.words.objects["тропа"], 1)
        self.assertEqual(state.bigrams.objects["экологическая тропа"], 1)
        self.assertEqual(state.highway_words.objects["исследователя"], 1)
        self.assertEqual(state.examples_by_tag["highway=path"][0]["id"], 42)

    def test_tracks_memorial_subtype_and_religion_breakdowns(self) -> None:
        state = AuditState()
        memorial_name = "Мемориальный комплекс защитникам города в годы Великой Отечественной войны"
        worship_name = "Храм во имя святого благоверного великого князя Александра Невского"
        missing_name = "Очень длинное наименование памятного объекта без указанного подтипа"

        add_name_to_state(
            state,
            name=memorial_name,
            tags={"historic": "memorial", "memorial": "war_memorial", "name": memorial_name},
            kind="node",
            geometry="-",
            object_id=10,
        )
        add_name_to_state(
            state,
            name=worship_name,
            tags={"amenity": "place_of_worship", "religion": "christian", "name": worship_name},
            kind="node",
            geometry="-",
            object_id=11,
        )
        add_name_to_state(
            state,
            name=missing_name,
            tags={"historic": "memorial", "name": missing_name},
            kind="node",
            geometry="-",
            object_id=12,
        )

        self.assertEqual(state.memorial_by_type["war_memorial"], 1)
        self.assertEqual(state.memorial_by_type["<missing>"], 1)
        self.assertEqual(state.place_of_worship_by_religion["christian"], 1)
        self.assertEqual(state.examples_by_memorial_type["war_memorial"][0]["id"], 10)
        self.assertEqual(state.examples_by_religion["christian"][0]["id"], 11)

    def test_short_name_is_ignored(self) -> None:
        state = AuditState()
        self.assertFalse(
            add_name_to_state(
                state,
                name="Короткое имя",
                tags={"amenity": "cafe"},
                kind="node",
                geometry="-",
                object_id=1,
                limit=30,
            )
        )
        self.assertEqual(state.long_names, 0)

    def test_term_rows_include_frequency_and_shortening_score(self) -> None:
        state = AuditState()
        for object_id in (1, 2):
            name = f"Очень длинная автомобильная дорога номер {object_id} через большой лесной массив"
            add_name_to_state(
                state,
                name=name,
                tags={"highway": "track"},
                kind="way",
                geometry="open_way",
                object_id=object_id,
            )
        rows = {row["term"]: row for row in _term_rows(state.words, 20)}
        self.assertEqual(rows["автомобильная"]["objects"], 2)
        self.assertEqual(rows["автомобильная"]["occurrences"], 2)
        self.assertGreater(rows["автомобильная"]["potential_saving_score"], 0)
        self.assertEqual(len(rows["автомобильная"]["examples"]), 2)


if __name__ == "__main__":
    unittest.main()

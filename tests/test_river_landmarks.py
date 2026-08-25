from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.river_landmarks import (
    enrich_river_landmark_tags,
    load_river_landmarks,
    normalize_river_name,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog/river-landmarks.tsv"


class RiverLandmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.landmarks = load_river_landmarks(CATALOG)

    def test_catalog_contains_expected_ranked_rivers(self) -> None:
        self.assertEqual(self.landmarks[normalize_river_name("Волга")], 1)
        self.assertEqual(self.landmarks[normalize_river_name("Ural")], 2)
        self.assertEqual(self.landmarks[normalize_river_name("Кубань")], 3)
        self.assertNotIn(normalize_river_name("Чусовая"), self.landmarks)

    def test_alias_and_local_name_match(self) -> None:
        tags, changed = enrich_river_landmark_tags(
            {"waterway": "river", "name": "Ертіс"}, self.landmarks
        )
        self.assertTrue(changed)
        self.assertEqual(tags["uralla:river_rank"], "1")

    def test_name_ru_can_match_when_primary_name_is_local(self) -> None:
        tags, changed = enrich_river_landmark_tags(
            {"waterway": "river", "name": "Жайық", "name:ru": "Урал"},
            self.landmarks,
        )
        self.assertTrue(changed)
        self.assertEqual(tags["uralla:river_rank"], "2")

    def test_non_river_with_same_name_is_not_enriched(self) -> None:
        tags, changed = enrich_river_landmark_tags(
            {"waterway": "stream", "name": "Волга"}, self.landmarks
        )
        self.assertFalse(changed)
        self.assertNotIn("uralla:river_rank", tags)

    def test_unlisted_river_is_unchanged(self) -> None:
        original = {"waterway": "river", "name": "Совсем малая река"}
        tags, changed = enrich_river_landmark_tags(original, self.landmarks)
        self.assertFalse(changed)
        self.assertEqual(tags, original)

    def test_conflicting_alias_ranks_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rivers.tsv"
            path.write_text(
                "rank\tlength_km\tname\taliases\torigin\n"
                "1\t4000\tAlpha\tSame\ttest\n"
                "2\t2000\tBeta\tSame\ttest\n",
                encoding="utf-8",
            )
            with self.assertRaises(StageError):
                load_river_landmarks(path)

    def test_rank_four_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "rivers.tsv"
            path.write_text(
                "rank\tlength_km\tname\taliases\torigin\n"
                "4\t500\tLegacy\t\ttest\n",
                encoding="utf-8",
            )
            with self.assertRaises(StageError):
                load_river_landmarks(path)


if __name__ == "__main__":
    unittest.main()

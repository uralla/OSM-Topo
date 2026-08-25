from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.preprocessor import (
    filter_tags,
    load_blacklist_rules,
    normalize_text,
    preprocess_pbf,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/preprocessor-blacklist.yaml"


class BlacklistPreprocessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = load_blacklist_rules(CONFIG, ["ru-political-parties"])

    def test_profile_uses_stable_wikidata_ids(self) -> None:
        rules = {rule.rule_id: rule for rule in self.rules}
        self.assertEqual(rules["united-russia"].wikidata, frozenset({"Q151469"}))
        self.assertEqual(rules["cprf"].wikidata, frozenset({"Q192187"}))

    def test_party_wikidata_neutralizes_all_tags(self) -> None:
        decision = filter_tags(
            {
                "office": "political_party",
                "name": "Региональное отделение",
                "wikidata": "Q151469",
                "addr:street": "Ленина",
            },
            self.rules,
        )
        self.assertEqual(decision.action, "neutralize")
        self.assertEqual(decision.tags, {})
        self.assertEqual(decision.matched_rules, ("united-russia",))

    def test_named_party_office_is_neutralized(self) -> None:
        decision = filter_tags(
            {
                "office": "politician",
                "name": "Приёмная депутата КПРФ",
                "phone": "+7 000 000-00-00",
            },
            self.rules,
        )
        self.assertEqual(decision.action, "neutralize")
        self.assertFalse(decision.tags)

    def test_incidental_mention_scrubs_only_matching_tag(self) -> None:
        decision = filter_tags(
            {
                "highway": "residential",
                "name": "Проезд возле офиса Единой России",
                "surface": "asphalt",
            },
            self.rules,
        )
        self.assertEqual(decision.action, "scrub")
        self.assertEqual(decision.tags, {"highway": "residential", "surface": "asphalt"})
        self.assertEqual(decision.removed_keys, ("name",))

    def test_exact_party_name_does_not_destroy_unrelated_road(self) -> None:
        decision = filter_tags(
            {"highway": "service", "name": "КПРФ", "access": "yes"},
            self.rules,
        )
        self.assertEqual(decision.action, "scrub")
        self.assertEqual(decision.tags, {"highway": "service", "access": "yes"})

    def test_domains_and_multilingual_tags_are_removed(self) -> None:
        decision = filter_tags(
            {
                "amenity": "community_centre",
                "contact:website": "https://kprf.ru/region",
                "name:en": "United Russia public reception",
                "name": "Общественная приёмная",
            },
            self.rules,
        )
        self.assertEqual(decision.action, "scrub")
        self.assertEqual(
            decision.tags,
            {"amenity": "community_centre", "name": "Общественная приёмная"},
        )

    def test_similar_words_and_ambiguous_abbreviation_are_not_removed(self) -> None:
        tags = {
            "name": "Единая улица России",
            "ref": "ЕР",
            "description": "единое российское пространство",
        }
        decision = filter_tags(tags, self.rules)
        self.assertEqual(decision.action, "none")
        self.assertEqual(decision.tags, tags)

    def test_normalization_handles_case_punctuation_and_yo(self) -> None:
        self.assertEqual(normalize_text("  ПАРТИЯ «Единая Россия»  "), "партия единая россия")
        decision = filter_tags({"description": "Штаб ЕдРо."}, self.rules)
        self.assertEqual(decision.action, "scrub")

    def test_real_osm_stream_is_written_and_verified(self) -> None:
        try:
            import osmium
        except ImportError:
            self.skipTest("optional osmium dependency is not installed")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.osm"
            output = root / "output.osm.pbf"
            report_path = root / "report.json"
            source.write_text(
                """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='uralla-test'>
  <node id='1' lat='55.0' lon='37.0' version='1'>
    <tag k='office' v='political_party'/>
    <tag k='name' v='Отделение КПРФ'/>
  </node>
  <node id='2' lat='55.1' lon='37.1' version='1'/>
  <node id='3' lat='55.2' lon='37.2' version='1'/>
  <way id='10' version='1'>
    <nd ref='2'/><nd ref='3'/>
    <tag k='highway' v='residential'/>
    <tag k='name' v='Проезд возле Единой России'/>
    <tag k='surface' v='asphalt'/>
  </way>
</osm>
""",
                encoding="utf-8",
            )

            report = preprocess_pbf(
                source,
                output,
                CONFIG,
                ["ru-political-parties"],
                report_path,
            )

            objects = {
                (item.type_str(), int(item.id)): dict(item.tags)
                for item in osmium.FileProcessor(str(output))
            }
            self.assertEqual(objects[("n", 1)], {})
            self.assertEqual(
                objects[("w", 10)],
                {"highway": "residential", "surface": "asphalt"},
            )
            self.assertEqual(report["neutralized_objects"], 1)
            self.assertEqual(report["scrubbed_objects"], 1)
            self.assertEqual(report["verified_forbidden_tags"], 0)
            self.assertTrue(report_path.is_file())


if __name__ == "__main__":
    unittest.main()

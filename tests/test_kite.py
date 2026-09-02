from pathlib import Path
import unittest

from uralla_build.kite import KITE_POI_TAG, enrich_kite_tags, is_kite_infrastructure


ROOT = Path(__file__).resolve().parents[1]


class KiteDetectorTests(unittest.TestCase):
    def test_accepts_russian_and_english_roots_in_any_value(self):
        self.assertTrue(is_kite_infrastructure({"brand": "Кайтшкола номер один"}))
        self.assertTrue(is_kite_infrastructure({"description": "Кайт станция и кайт школа ВиндЭкстрим"}))
        self.assertTrue(is_kite_infrastructure({"designation": "Kitesurfing"}))
        self.assertTrue(is_kite_infrastructure({"name": 'Школа кайтсерфинга "Точка отрыва"'}))
        self.assertTrue(is_kite_infrastructure({"name": 'Кайтспот "Гуровская гора"', "tourism": "viewpoint"}))
        self.assertTrue(is_kite_infrastructure({"operator": "Kite Station"}))

    def test_accepts_prefixed_compounds_and_tag_keys(self):
        self.assertTrue(is_kite_infrastructure({"sport": "snowkite"}))
        self.assertTrue(is_kite_infrastructure({"description": "Landkite school"}))
        self.assertTrue(is_kite_infrastructure({"kitesurfing": "yes"}))
        self.assertTrue(is_kite_infrastructure({"service:snowkite": "yes"}))

    def test_rejects_unrelated_words_and_derived_tag_alone(self):
        self.assertFalse(is_kite_infrastructure({"name": "Nikita"}))
        self.assertFalse(is_kite_infrastructure({"description": "обычная школа серфинга"}))
        self.assertFalse(is_kite_infrastructure({KITE_POI_TAG: "no"}))

    def test_enrichment_writes_stable_style_tag(self):
        tags, changed = enrich_kite_tags({"description": "kite school"})
        self.assertTrue(changed)
        self.assertEqual(tags[KITE_POI_TAG], "yes")

    def test_kite_style_precedes_viewpoint_style(self):
        style = (ROOT / "styles/uralla/inc/priority_points").read_text(encoding="utf-8")
        self.assertLess(
            style.index("uralla:kite=yes"),
            style.index("tourism=viewpoint & name=*"),
        )

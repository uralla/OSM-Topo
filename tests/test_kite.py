from uralla_build.kite import KITE_POI_TAG, enrich_kite_tags, is_kite_infrastructure


def test_kite_detector_accepts_russian_and_english_roots_in_any_value():
    assert is_kite_infrastructure({"brand": "Кайтшкола номер один"})
    assert is_kite_infrastructure({"description": "Кайт станция и кайт школа ВиндЭкстрим"})
    assert is_kite_infrastructure({"designation": "Kitesurfing"})
    assert is_kite_infrastructure({"name": 'Школа кайтсерфинга "Точка отрыва"'})
    assert is_kite_infrastructure({"operator": "Kite Station"})


def test_kite_detector_requires_a_word_start_not_an_internal_substring():
    assert not is_kite_infrastructure({"name": "Nikita"})
    assert not is_kite_infrastructure({"description": "обычная школа серфинга"})


def test_kite_enrichment_writes_stable_style_tag():
    tags, changed = enrich_kite_tags({"description": "kite school"})
    assert changed
    assert tags[KITE_POI_TAG] == "yes"

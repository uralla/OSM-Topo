from uralla_build.sanatorium_labels import enrich_sanatorium_label_tags


def test_sanatorium_academic_name_is_compacted_without_initials():
    tags, changed = enrich_sanatorium_label_tags(
        {
            "healthcare": "sanatorium",
            "name": "Санаторий имени академика Н. Н. Бурденко",
        }
    )
    assert changed
    assert tags["uralla:label"] == "Сан. им. академика Бурденко"
    assert tags["name"] == "Санаторий имени академика Н. Н. Бурденко"


def test_non_sanatorium_name_is_untouched():
    tags, changed = enrich_sanatorium_label_tags(
        {"name": "Санаторий имени академика Н. Н. Бурденко"}
    )
    assert not changed
    assert "uralla:label" not in tags

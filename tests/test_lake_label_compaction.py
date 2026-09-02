from uralla_build.preprocessor import enrich_geographic_label_tags


def test_lake_size_prefix_drops_redundant_trailing_type():
    tags, changed = enrich_geographic_label_tags(
        {"natural": "water", "water": "lake", "name": "Большое Катасьминское озеро"}
    )
    assert changed
    assert tags["uralla:label"] == "Бол. Катасьминское"
    assert tags["name"] == "Большое Катасьминское озеро"


def test_lake_proper_name_suffix_is_preserved_without_generic_size_prefix():
    tags, changed = enrich_geographic_label_tags(
        {"natural": "water", "water": "lake", "name": "Черное Озеро"}
    )
    assert not changed
    assert "uralla:label" not in tags

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Shared semantic detector for context indexing.
replace_once(
    "uralla_build/poi_context.py",
    "from .poi_lod import POI_LOD_CLASS_TAG, classify_poi_lod, intrinsic_floor_for_poi\n",
    "from .kite import is_kite_infrastructure\nfrom .poi_lod import POI_LOD_CLASS_TAG, classify_poi_lod, intrinsic_floor_for_poi\n",
)
replace_once(
    "uralla_build/poi_context.py",
    '''def is_kitesurfing(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("sport") == "kitesurfing"\n''',
    '''def is_kitesurfing(tags: Mapping[str, str] | object) -> bool:\n    # Compatibility name for the adaptive outdoor-context branch. Detection is\n    # deliberately semantic because real OSM kite spots/stations are tagged very\n    # inconsistently (sport, name, brand, description, designation, etc.).\n    return is_kite_infrastructure(tags)\n''',
)

# Area -> POI must use exactly the same semantic detector as real nodes so a real
# kite point inside an eligible kite polygon suppresses the synthetic duplicate.
replace_once(
    "uralla_build/area_pois.py",
    "from uuid import uuid4\n",
    "from uuid import uuid4\n\nfrom .kite import is_kite_infrastructure\n",
)
replace_once(
    "uralla_build/area_pois.py",
    '''    if tags.get("sport") == "kitesurfing":\n        return "sport:kitesurfing"\n''',
    '''    if is_kite_infrastructure(tags):\n        return "kite:infrastructure"\n''',
)

# Add a stable semantic tag before adaptive LOD enrichment; the style no longer
# depends on whichever source tag happened to contain the kite marker.
replace_once(
    "uralla_build/preprocessor.py",
    "from .errors import StageError\n",
    "from .errors import StageError\nfrom .kite import enrich_kite_tags\n",
)
replace_once(
    "uralla_build/preprocessor.py",
    '''                final_tags, _long_name_added = enrich_long_name_tags(final_tags)\n                final_tags, peak_added = enrich_peak_landmark_tags(\n''',
    '''                final_tags, _long_name_added = enrich_long_name_tags(final_tags)\n                final_tags, kite_added = enrich_kite_tags(final_tags)\n                if kite_added:\n                    counters["kite_infrastructure_enriched"] += 1\n                final_tags, peak_added = enrich_peak_landmark_tags(\n''',
)

# Remove the final stale object-specific Solnyshko exception while touching this
# block: only non-common accommodation diagnostics should be emitted.
replace_once(
    "uralla_build/preprocessor.py",
    '''                        and (\n                            accommodation_priority != "common"\n                            or normalize_text(str(accommodation_sample.get("name"))) == "солнышко"\n                        )\n''',
    '''                        and accommodation_priority != "common"\n''',
)

# Garmin style: one semantic class, one reserved POI type, adaptive H/M/L.
p = Path("styles/uralla/inc/priority_points")
text = p.read_text(encoding="utf-8")
text = text.replace(
    "uralla:poi_lod_class=H & sport=kitesurfing { name '${name}' | 'кайты' } [0x6609 resolution 22]",
    "uralla:poi_lod_class=H & uralla:kite=yes { name '${name}' | 'кайт' } [0x6609 resolution 22]",
)
text = text.replace(
    "uralla:poi_lod_class=M & sport=kitesurfing { name '${name}' | 'кайты' } [0x6609 resolution 23]",
    "uralla:poi_lod_class=M & uralla:kite=yes { name '${name}' | 'кайт' } [0x6609 resolution 23]",
)
text = text.replace(
    "uralla:poi_lod_class=L & sport=kitesurfing { name '${name}' | 'кайты' } [0x6609 resolution 24]",
    "uralla:poi_lod_class=L & uralla:kite=yes { name '${name}' | 'кайт' } [0x6609 resolution 24]",
)
text = text.replace(
    "sport=kitesurfing { name '${name}' | 'кайты' } [0x6609 resolution 24]",
    "uralla:kite=yes { name '${name}' | 'кайт' } [0x6609 resolution 24]",
)
p.write_text(text, encoding="utf-8")

# TYP placeholder designation follows the agreed unnamed label.
replace_once(
    "styles/uralla.txt",
    "String1=0x19,кайты\nString2=0x04,kitesurfing",
    "String1=0x19,кайт\nString2=0x04,kitesurfing",
)

# Area tests now exercise inconsistent real-world tagging rather than one schema.
p = Path("tests/test_area_pois.py")
text = p.read_text(encoding="utf-8")
old = '''def test_kitesurfing_area_is_eligible_for_poi():\n    from uralla_build.area_pois import area_poi_kind\n\n    assert area_poi_kind({"sport": "kitesurfing"}) == "sport:kitesurfing"\n'''
new = '''def test_kite_areas_are_eligible_across_inconsistent_tagging():\n    assert area_poi_kind({"sport": "kitesurfing"}) == "kite:infrastructure"\n    assert area_poi_kind({"brand": "Кайтшкола номер один"}) == "kite:infrastructure"\n    assert area_poi_kind({"designation": "Kitesurfing"}) == "kite:infrastructure"\n    assert area_poi_kind({"name": 'Школа кайтсерфинга "Точка отрыва"'}) == "kite:infrastructure"\n    assert area_poi_kind({"description": "Кайт станция и прокат оборудования"}) == "kite:infrastructure"\n'''
if old not in text:
    raise SystemExit("old kitesurfing area test not found")
p.write_text(text.replace(old, new, 1), encoding="utf-8")

# Focused detector tests, including negatives that protect against accidental substring matches.
Path("tests/test_kite.py").write_text(
    '''from uralla_build.kite import KITE_POI_TAG, enrich_kite_tags, is_kite_infrastructure\n\n\ndef test_kite_detector_accepts_russian_and_english_roots_in_any_value():\n    assert is_kite_infrastructure({"brand": "Кайтшкола номер один"})\n    assert is_kite_infrastructure({"description": "Кайт станция и кайт школа ВиндЭкстрим"})\n    assert is_kite_infrastructure({"designation": "Kitesurfing"})\n    assert is_kite_infrastructure({"name": 'Школа кайтсерфинга "Точка отрыва"'})\n    assert is_kite_infrastructure({"operator": "Kite Station"})\n\n\ndef test_kite_detector_requires_a_word_start_not_an_internal_substring():\n    assert not is_kite_infrastructure({"name": "Nikita"})\n    assert not is_kite_infrastructure({"description": "обычная школа серфинга"})\n\n\ndef test_kite_enrichment_writes_stable_style_tag():\n    tags, changed = enrich_kite_tags({"description": "kite school"})\n    assert changed\n    assert tags[KITE_POI_TAG] == "yes"\n''',
    encoding="utf-8",
)

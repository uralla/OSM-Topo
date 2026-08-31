from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match, got {count}"
    return text.replace(old, new, 1)

# --- poi_context.py ---
p = Path('uralla_build/poi_context.py')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    'OUTDOOR_FURNITURE_VALUES = frozenset({"bench", "picnic_table"})\n',
    'OUTDOOR_FURNITURE_VALUES = frozenset({"bench", "picnic_table"})\nTOURIST_RETAIL_VALUES = frozenset({"bicycle", "hardware", "doityourself", "houseware", "sports", "outdoor"})\n',
    'retail values',
)
s = replace_once(
    s,
    'def is_outdoor_furniture(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("amenity") == "bench" or values.get("leisure") == "picnic_table"\n\n\n',
    'def is_outdoor_furniture(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("amenity") == "bench" or values.get("leisure") == "picnic_table"\n\n\ndef is_tourist_retail(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("shop") in TOURIST_RETAIL_VALUES\n\n\n',
    'retail predicate',
)
s = replace_once(
    s,
    '    outdoor_furniture: FoodShopIndex\n    activity: FoodShopIndex\n',
    '    outdoor_furniture: FoodShopIndex\n    tourist_retail: FoodShopIndex\n    activity: FoodShopIndex\n',
    'context field',
)
s = replace_once(
    s,
    '    outdoor_furniture = FoodShopIndex.empty()\n    activity = FoodShopIndex.empty()\n',
    '    outdoor_furniture = FoodShopIndex.empty()\n    tourist_retail = FoodShopIndex.empty()\n    activity = FoodShopIndex.empty()\n',
    'retail index init',
)
s = replace_once(
    s,
    '        if is_outdoor_furniture(tags):\n            outdoor_furniture.add(*location)\n            adaptive = True\n        if adaptive:\n',
    '        if is_outdoor_furniture(tags):\n            outdoor_furniture.add(*location)\n            adaptive = True\n        if is_tourist_retail(tags):\n            tourist_retail.add(*location)\n            adaptive = True\n        if adaptive:\n',
    'retail index populate',
)
s = replace_once(
    s,
    '    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, activity, screen_pressure, places, adaptive_candidates)\n',
    '    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, tourist_retail, activity, screen_pressure, places, adaptive_candidates)\n',
    'context return',
)
insert_after = '''def enrich_outdoor_context(\n    item: object,\n    tags: Mapping[str, str] | object,\n    index: FoodShopIndex,\n    *,\n    kind: str,\n) -> tuple[dict[str, str], bool, dict[str, object] | None]:\n'''
assert insert_after in s
# Add retail handling by extending the match choice and retaining the same rarity thresholds.
s = replace_once(
    s,
    '    matches = is_picnic_site(result) if kind == "picnic" else is_outdoor_furniture(result)\n',
    '    if kind == "picnic":\n        matches = is_picnic_site(result)\n    elif kind == "furniture":\n        matches = is_outdoor_furniture(result)\n    elif kind == "retail":\n        matches = is_tourist_retail(result)\n    else:\n        raise ValueError(f"unknown outdoor context kind: {kind}")\n',
    'retail enrichment match',
)
p.write_text(s, encoding='utf-8')

# --- poi_lod.py ---
p = Path('uralla_build/poi_lod.py')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    '    if tags.get("shop") == "supermarket" or tags.get("amenity") == "supermarket":\n        return "M"\n',
    '    if tags.get("shop") in {"supermarket", "bicycle"} or tags.get("amenity") == "supermarket":\n        return "M"\n',
    'bicycle intrinsic floor',
)
p.write_text(s, encoding='utf-8')

# --- preprocessor.py ---
p = Path('uralla_build/preprocessor.py')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    '    outdoor_furniture_index = context_indexes.outdoor_furniture\n    activity_index = context_indexes.activity\n',
    '    outdoor_furniture_index = context_indexes.outdoor_furniture\n    tourist_retail_index = context_indexes.tourist_retail\n    activity_index = context_indexes.activity\n',
    'retail index local',
)
s = replace_once(
    s,
    '        f"furniture {outdoor_furniture_index.shop_count:,}; "\n        f"activity {activity_index.shop_count:,}; "\n',
    '        f"furniture {outdoor_furniture_index.shop_count:,}; "\n        f"retail {tourist_retail_index.shop_count:,}; "\n        f"activity {activity_index.shop_count:,}; "\n',
    'retail index log',
)
s = replace_once(
    s,
    '                final_tags, furniture_added, _furniture_sample = enrich_outdoor_context(\n                    item, final_tags, outdoor_furniture_index, kind="furniture"\n                )\n                if furniture_added:\n                    counters["furniture_context_enriched"] += 1\n\n                final_tags, activity_added, activity_sample = enrich_activity_diagnostics(\n',
    '                final_tags, furniture_added, _furniture_sample = enrich_outdoor_context(\n                    item, final_tags, outdoor_furniture_index, kind="furniture"\n                )\n                if furniture_added:\n                    counters["furniture_context_enriched"] += 1\n\n                final_tags, retail_added, _retail_sample = enrich_outdoor_context(\n                    item, final_tags, tourist_retail_index, kind="retail"\n                )\n                if retail_added:\n                    counters["retail_context_enriched"] += 1\n\n                final_tags, activity_added, activity_sample = enrich_activity_diagnostics(\n',
    'retail writer enrichment',
)
p.write_text(s, encoding='utf-8')

# --- priority_points style ---
p = Path('styles/uralla/inc/priority_points')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    '''# Bicycle shop remains a distinct tourist-useful POI.\n# [CUSTOM/АВТОРСКОЕ] Bicycle services use a dedicated visible-label POI.\nshop=bicycle { name '${name}' | 'велосипеды' } [0x2f18 resolution 23]\n''',
    '''# Bicycle shop remains a distinct tourist-useful POI and uses adaptive LOD.\nuralla:poi_lod_class=H & shop=bicycle { name '${name}' | 'велосипеды' } [0x2f18 resolution 22]\nuralla:poi_lod_class=M & shop=bicycle { name '${name}' | 'велосипеды' } [0x2f18 resolution 23]\nuralla:poi_lod_class=L & shop=bicycle { name '${name}' | 'велосипеды' } [0x2f18 resolution 24]\nshop=bicycle { name '${name}' | 'велосипеды' } [0x2f18 resolution 23]\n''',
    'bicycle adaptive style',
)
s = replace_once(
    s,
    '''(shop=hardware | shop=doityourself | shop=houseware) { name '${name}' | 'хозтовары' } [0x2e00 resolution 24]\n(shop=sports | shop=outdoor) { name '${name}' | 'спорттовары' } [0x2e00 resolution 24]\n''',
    '''uralla:poi_lod_class=H & (shop=hardware | shop=doityourself | shop=houseware) { name '${name}' | 'хозтовары' } [0x2e00 resolution 22]\nuralla:poi_lod_class=M & (shop=hardware | shop=doityourself | shop=houseware) { name '${name}' | 'хозтовары' } [0x2e00 resolution 23]\nuralla:poi_lod_class=L & (shop=hardware | shop=doityourself | shop=houseware) { name '${name}' | 'хозтовары' } [0x2e00 resolution 24]\n(shop=hardware | shop=doityourself | shop=houseware) { name '${name}' | 'хозтовары' } [0x2e00 resolution 24]\nuralla:poi_lod_class=H & (shop=sports | shop=outdoor) { name '${name}' | 'спорттовары' } [0x2e00 resolution 22]\nuralla:poi_lod_class=M & (shop=sports | shop=outdoor) { name '${name}' | 'спорттовары' } [0x2e00 resolution 23]\nuralla:poi_lod_class=L & (shop=sports | shop=outdoor) { name '${name}' | 'спорттовары' } [0x2e00 resolution 24]\n(shop=sports | shop=outdoor) { name '${name}' | 'спорттовары' } [0x2e00 resolution 24]\n''',
    'support retail adaptive style',
)
p.write_text(s, encoding='utf-8')

# --- polygon building hover fallback ---
p = Path('styles/uralla/polygons')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    "(building=* | bridge=yes & area=yes) \t{name '${name}' | '${addr:street} ${addr:housenumber}' | '${addr:housenumber}' } [0x13 resolution 24]\n",
    "building=* \t{name '${name}' | '${addr:street} ${addr:housenumber}' | '${addr:housenumber}' | 'здание' } [0x13 resolution 24]\nbridge=yes & area=yes \t{name '${name}' | '${addr:street} ${addr:housenumber}' | '${addr:housenumber}' } [0x13 resolution 24]\n",
    'building fallback label',
)
p.write_text(s, encoding='utf-8')

# --- tests ---
p = Path('tests/test_poi_context.py')
s = p.read_text(encoding='utf-8')
if 'is_tourist_retail' not in s:
    # Import alongside existing poi_context imports using a conservative insertion.
    s = s.replace('    is_outdoor_furniture,\n', '    is_outdoor_furniture,\n    is_tourist_retail,\n', 1)
    s += '''\n\ndef test_tourist_retail_whitelist_is_adaptive():\n    for value in ("bicycle", "hardware", "doityourself", "houseware", "sports", "outdoor"):\n        assert is_tourist_retail({"shop": value})\n    for value in ("books", "mobile_phone", "medical_supply"):\n        assert not is_tourist_retail({"shop": value})\n'''
p.write_text(s, encoding='utf-8')

p = Path('tests/test_poi_lod.py')
s = p.read_text(encoding='utf-8')
if 'test_bicycle_intrinsic_floor_is_medium' not in s:
    s += '''\n\ndef test_bicycle_intrinsic_floor_is_medium():\n    assert intrinsic_floor_for_poi({"shop": "bicycle"}) == "M"\n'''
p.write_text(s, encoding='utf-8')

Path('tests/test_building_hover_label.py').write_text('''from pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\nPOLYGONS = ROOT / "styles" / "uralla" / "polygons"\nTYP = ROOT / "styles" / "uralla.txt"\n\ndef test_unnamed_building_has_explicit_hover_fallback():\n    style = POLYGONS.read_text(encoding="utf-8")\n    assert "building=* \\t{name '${name}' | '${addr:street} ${addr:housenumber}' | '${addr:housenumber}' | 'здание' } [0x13 resolution 24]" in style\n    assert "String1=0x19,здание" in TYP.read_text(encoding="utf-8")\n''', encoding='utf-8')

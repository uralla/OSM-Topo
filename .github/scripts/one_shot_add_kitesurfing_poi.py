from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"anchor not unique in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- poi_context: dedicated adaptive index for kitesurfing -----------------
p = "uralla_build/poi_context.py"
replace_once(
    p,
    'def is_spring(tags: Mapping[str, str] | object) -> bool:\n',
    'def is_kitesurfing(tags: Mapping[str, str] | object) -> bool:\n'
    '    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n'
    '    values = {str(key): str(value) for key, value in items}\n'
    '    return values.get("sport") == "kitesurfing"\n\n\n'
    'def is_spring(tags: Mapping[str, str] | object) -> bool:\n',
)
replace_once(
    p,
    '    tourist_retail: FoodShopIndex\n    spring: FoodShopIndex\n',
    '    tourist_retail: FoodShopIndex\n    kitesurfing: FoodShopIndex\n    spring: FoodShopIndex\n',
)
replace_once(
    p,
    '    tourist_retail = FoodShopIndex.empty()\n    spring = FoodShopIndex.empty()\n',
    '    tourist_retail = FoodShopIndex.empty()\n    kitesurfing = FoodShopIndex.empty()\n    spring = FoodShopIndex.empty()\n',
)
replace_once(
    p,
    '        if is_tourist_retail(tags):\n            tourist_retail.add(*location)\n            adaptive = True\n        if is_spring(tags):\n',
    '        if is_tourist_retail(tags):\n            tourist_retail.add(*location)\n            adaptive = True\n        if is_kitesurfing(tags):\n            kitesurfing.add(*location)\n            adaptive = True\n        if is_spring(tags):\n',
)
replace_once(
    p,
    '    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, tourist_retail, spring, activity, screen_pressure, places, adaptive_candidates)\n',
    '    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, tourist_retail, kitesurfing, spring, activity, screen_pressure, places, adaptive_candidates)\n',
)
replace_once(
    p,
    '    elif kind == "retail":\n        matches = is_tourist_retail(result)\n    elif kind == "spring":\n',
    '    elif kind == "retail":\n        matches = is_tourist_retail(result)\n    elif kind == "kitesurfing":\n        matches = is_kitesurfing(result)\n    elif kind == "spring":\n',
)

# --- preprocessor: run kitesurfing through the same H/M/L pipeline ---------
p = "uralla_build/preprocessor.py"
replace_once(
    p,
    '    tourist_retail_index = context_indexes.tourist_retail\n    spring_index = context_indexes.spring\n',
    '    tourist_retail_index = context_indexes.tourist_retail\n    kitesurfing_index = context_indexes.kitesurfing\n    spring_index = context_indexes.spring\n',
)
replace_once(
    p,
    '        f"retail {tourist_retail_index.shop_count:,}; "\n        f"spring {spring_index.shop_count:,}; "\n',
    '        f"retail {tourist_retail_index.shop_count:,}; "\n        f"kitesurfing {kitesurfing_index.shop_count:,}; "\n        f"spring {spring_index.shop_count:,}; "\n',
)
replace_once(
    p,
    '                final_tags, spring_added, _spring_sample = enrich_outdoor_context(\n                    item, final_tags, spring_index, kind="spring"\n                )\n',
    '                final_tags, kitesurfing_added, _kitesurfing_sample = enrich_outdoor_context(\n                    item, final_tags, kitesurfing_index, kind="kitesurfing"\n                )\n                if kitesurfing_added:\n                    counters["kitesurfing_context_enriched"] += 1\n\n'
    '                final_tags, spring_added, _spring_sample = enrich_outdoor_context(\n                    item, final_tags, spring_index, kind="spring"\n                )\n',
)

# --- area -> POI whitelist --------------------------------------------------
p = "uralla_build/area_pois.py"
replace_once(
    p,
    '    if tags.get("office") == "government":\n',
    '    if tags.get("sport") == "kitesurfing":\n        return "sport:kitesurfing"\n\n    if tags.get("office") == "government":\n',
)

# --- mkgmap point style -----------------------------------------------------
p = "styles/uralla/inc/priority_points"
replace_once(
    p,
    '# Small tourist infrastructure.\nleisure=picnic_table [0x4a01 resolution 24]\n',
    '# Kitesurfing spots: dedicated adaptive POI. Unnamed spots use a compact designation.\n'
    'uralla:poi_lod_class=H & sport=kitesurfing { name \'${name}\' | \'кайты\' } [0x6609 resolution 22]\n'
    'uralla:poi_lod_class=M & sport=kitesurfing { name \'${name}\' | \'кайты\' } [0x6609 resolution 23]\n'
    'uralla:poi_lod_class=L & sport=kitesurfing { name \'${name}\' | \'кайты\' } [0x6609 resolution 24]\n'
    'sport=kitesurfing { name \'${name}\' | \'кайты\' } [0x6609 resolution 24]\n\n'
    '# Small tourist infrastructure.\nleisure=picnic_table [0x4a01 resolution 24]\n',
)

# --- TYP placeholder: simple blue circle on free custom POI 0x6609 --------
p = "styles/uralla.txt"
typ_block = r'''[_point]
Type=0x066
SubType=0x09
; CUSTOM: kitesurfing placeholder. Reserved for final user-drawn icon.
String1=0x19,кайты
String2=0x04,kitesurfing
ExtendedLabels=Y
FontStyle=SmallFont
CustomColor=No
ContourColor=No
DayXpm="16 16 2 1"   Colormode=16
"  c none"
"! c #0066FF"
"                "
"                "
"      !!!!      "
"    !!!!!!!!    "
"   !!!!!!!!!!   "
"   !!!!!!!!!!   "
"  !!!!!!!!!!!!  "
"  !!!!!!!!!!!!  "
"  !!!!!!!!!!!!  "
"  !!!!!!!!!!!!  "
"   !!!!!!!!!!   "
"   !!!!!!!!!!   "
"    !!!!!!!!    "
"      !!!!      "
"                "
"                "
;1234567890123456
[end]


'''
replace_once(
    p,
    '[_point]\nType=0x066\nSubType=0x0f\n',
    typ_block + '[_point]\nType=0x066\nSubType=0x0f\n',
)

# --- tests -----------------------------------------------------------------
p = "tests/test_area_pois.py"
text = Path(p).read_text(encoding="utf-8")
if 'sport:kitesurfing' not in text:
    text += '''\n\ndef test_kitesurfing_area_is_eligible_for_poi():\n    from uralla_build.area_pois import area_poi_kind\n\n    assert area_poi_kind({"sport": "kitesurfing"}) == "sport:kitesurfing"\n'''
    Path(p).write_text(text, encoding="utf-8")

print("kitesurfing POI patch applied")

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- Adaptive natural=spring context ---------------------------------------
path = "uralla_build/poi_context.py"
replace_once(
    path,
    'def is_tourist_retail(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("shop") in TOURIST_RETAIL_VALUES\n',
    'def is_tourist_retail(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("shop") in TOURIST_RETAIL_VALUES\n\n\ndef is_spring(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("natural") == "spring"\n'
)
replace_once(
    path,
    '    tourist_retail: FoodShopIndex\n    activity: FoodShopIndex\n',
    '    tourist_retail: FoodShopIndex\n    spring: FoodShopIndex\n    activity: FoodShopIndex\n'
)
replace_once(
    path,
    '    tourist_retail = FoodShopIndex.empty()\n    activity = FoodShopIndex.empty()\n',
    '    tourist_retail = FoodShopIndex.empty()\n    spring = FoodShopIndex.empty()\n    activity = FoodShopIndex.empty()\n'
)
replace_once(
    path,
    '        if is_tourist_retail(tags):\n            tourist_retail.add(*location)\n            adaptive = True\n        if adaptive:\n',
    '        if is_tourist_retail(tags):\n            tourist_retail.add(*location)\n            adaptive = True\n        if is_spring(tags):\n            spring.add(*location)\n            adaptive = True\n        if adaptive:\n'
)
replace_once(
    path,
    '    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, tourist_retail, activity, screen_pressure, places, adaptive_candidates)\n',
    '    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, tourist_retail, spring, activity, screen_pressure, places, adaptive_candidates)\n'
)
replace_once(
    path,
    '    elif kind == "retail":\n        matches = is_tourist_retail(result)\n    else:\n',
    '    elif kind == "retail":\n        matches = is_tourist_retail(result)\n    elif kind == "spring":\n        matches = is_spring(result)\n    else:\n'
)

# --- Preprocessor wiring ----------------------------------------------------
path = "uralla_build/preprocessor.py"
replace_once(
    path,
    '    tourist_retail_index = context_indexes.tourist_retail\n    activity_index = context_indexes.activity\n',
    '    tourist_retail_index = context_indexes.tourist_retail\n    spring_index = context_indexes.spring\n    activity_index = context_indexes.activity\n'
)
replace_once(
    path,
    '        f"retail {tourist_retail_index.shop_count:,}; "\n        f"activity {activity_index.shop_count:,}; "\n',
    '        f"retail {tourist_retail_index.shop_count:,}; "\n        f"spring {spring_index.shop_count:,}; "\n        f"activity {activity_index.shop_count:,}; "\n'
)
replace_once(
    path,
    '                final_tags, retail_added, _retail_sample = enrich_outdoor_context(\n                    item, final_tags, tourist_retail_index, kind="retail"\n                )\n                if retail_added:\n                    counters["retail_context_enriched"] += 1\n\n                final_tags, activity_added, activity_sample = enrich_activity_diagnostics(',
    '                final_tags, retail_added, _retail_sample = enrich_outdoor_context(\n                    item, final_tags, tourist_retail_index, kind="retail"\n                )\n                if retail_added:\n                    counters["retail_context_enriched"] += 1\n\n                final_tags, spring_added, _spring_sample = enrich_outdoor_context(\n                    item, final_tags, spring_index, kind="spring"\n                )\n                if spring_added:\n                    counters["spring_context_enriched"] += 1\n\n                final_tags, activity_added, activity_sample = enrich_activity_diagnostics('
)

# --- Style: springs ---------------------------------------------------------
path = "styles/uralla/inc/water_points"
replace_once(
    path,
    '(man_made=water_well | man_made=water_tap | amenity=drinking_water | natural=spring)\n    & intermittent!=yes & !(seasonal=* & seasonal!=no)\n    [0x6511 resolution 22]\n\n(man_made=water_well | man_made=water_tap | amenity=drinking_water | natural=spring)\n    & (intermittent=yes | (seasonal=* & seasonal!=no))\n    { name \'${name|subst: (сезонный)=>|subst: (Сезонный)=>} (пересых.)\' | \'пересых. источник\' }\n    [0x6512 resolution 23]\n',
    '# Springs use the shared adaptive POI LOD (H=22, M=23, L=24). Other water\n# source classes retain their established fixed visibility.\n(man_made=water_well | man_made=water_tap | amenity=drinking_water)\n    & intermittent!=yes & !(seasonal=* & seasonal!=no)\n    [0x6511 resolution 22]\n(man_made=water_well | man_made=water_tap | amenity=drinking_water)\n    & (intermittent=yes | (seasonal=* & seasonal!=no))\n    { name \'${name|subst: (сезонный)=>|subst: (Сезонный)=>} (пересых.)\' | \'пересых. источник\' }\n    [0x6512 resolution 23]\n\nuralla:poi_lod_class=H & natural=spring & intermittent!=yes & !(seasonal=* & seasonal!=no) [0x6511 resolution 22]\nuralla:poi_lod_class=M & natural=spring & intermittent!=yes & !(seasonal=* & seasonal!=no) [0x6511 resolution 23]\nuralla:poi_lod_class=L & natural=spring & intermittent!=yes & !(seasonal=* & seasonal!=no) [0x6511 resolution 24]\nnatural=spring & intermittent!=yes & !(seasonal=* & seasonal!=no) [0x6511 resolution 24]\n\nuralla:poi_lod_class=H & natural=spring & (intermittent=yes | (seasonal=* & seasonal!=no)) { name \'${name|subst: (сезонный)=>|subst: (Сезонный)=>} (пересых.)\' | \'пересых. источник\' } [0x6512 resolution 22]\nuralla:poi_lod_class=M & natural=spring & (intermittent=yes | (seasonal=* & seasonal!=no)) { name \'${name|subst: (сезонный)=>|subst: (Сезонный)=>} (пересых.)\' | \'пересых. источник\' } [0x6512 resolution 23]\nuralla:poi_lod_class=L & natural=spring & (intermittent=yes | (seasonal=* & seasonal!=no)) { name \'${name|subst: (сезонный)=>|subst: (Сезонный)=>} (пересых.)\' | \'пересых. источник\' } [0x6512 resolution 24]\nnatural=spring & (intermittent=yes | (seasonal=* & seasonal!=no)) { name \'${name|subst: (сезонный)=>|subst: (Сезонный)=>} (пересых.)\' | \'пересых. источник\' } [0x6512 resolution 24]\n'
)

# --- Style: marketplace polygon + centre POI -------------------------------
path = "styles/uralla/polygons"
replace_once(
    path,
    'amenity=supermarket & building!=* [0x08 resolution 22]\namenity=university & building!=* [0x0a resolution 22 continue]\n',
    'amenity=supermarket & building!=* [0x08 resolution 22]\n# Marketplaces are retail areas; keep both overview and close-detail fills.\namenity=marketplace & building!=* [0x08 resolution 22-23 continue]\namenity=marketplace & building!=* [0x10909 resolution 24]\namenity=university & building!=* [0x0a resolution 22 continue]\n'
)
path = "styles/uralla/inc/priority_points"
text = Path(path).read_text(encoding="utf-8")
anchor = '# Parcel pickup points: current OSM tags plus the deprecated vending-machine form.\n'
if anchor not in text:
    raise SystemExit(f"marketplace POI anchor not found in {path}")
text = text.replace(anchor, "# Marketplaces: node POIs and area-derived centre POIs use one shopping symbol.\namenity=marketplace { name '${name}' | 'рынок' } [0x2e00 resolution 23]\n\n" + anchor, 1)
Path(path).write_text(text, encoding="utf-8")

# --- Style: power lines one level closer -----------------------------------
path = "styles/uralla/lines"
replace_once(
    path,
    'power=line & length()>500 [0x29 resolution 21-23 continue]\n',
    'power=line & length()>500 [0x29 resolution 22-23 continue]\n'
)

print("one-shot spring/marketplace/power patch applied")

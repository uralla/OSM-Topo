from pathlib import Path

# ---- poi_context.py ----
p = Path('uralla_build/poi_context.py')
s = p.read_text(encoding='utf-8')

anchor = 'TRANSIT_STOP_HIGHWAYS = frozenset({"bus_stop"})\n'
assert anchor in s
s = s.replace(anchor, anchor + 'PICNIC_SITE_VALUES = frozenset({"picnic_site"})\nOUTDOOR_FURNITURE_VALUES = frozenset({"bench", "picnic_table"})\n', 1)

anchor = '''def is_transit_stop(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    if values.get("highway") in TRANSIT_STOP_HIGHWAYS:\n        return True\n    return (\n        values.get("public_transport") == "platform"\n        and (values.get("bus") == "yes" or values.get("trolleybus") == "yes")\n    )\n\n\n'''
assert anchor in s
addition = '''def is_picnic_site(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("tourism") in PICNIC_SITE_VALUES\n\n\ndef is_outdoor_furniture(tags: Mapping[str, str] | object) -> bool:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    values = {str(key): str(value) for key, value in items}\n    return values.get("amenity") == "bench" or values.get("leisure") == "picnic_table"\n\n\ndef classify_outdoor_rarity(*, objects_2km: int, objects_10km: int) -> tuple[str, str]:\n    if objects_2km <= 1 and objects_10km <= 10:\n        return "remote", "isolated"\n    if objects_2km <= 3 and objects_10km <= 25:\n        return "settlement", "sparse"\n    return "urban", "common"\n\n\n'''
s = s.replace(anchor, anchor + addition, 1)

old = '''class ContextIndexes:\n    food: FoodShopIndex\n    accommodation: FoodShopIndex\n    transit: FoodShopIndex\n    activity: FoodShopIndex\n    screen_pressure: WeightedPointIndex\n    places: PlaceAnchorIndex\n    adaptive_candidates: list[tuple[int, float, float]]\n'''
new = '''class ContextIndexes:\n    food: FoodShopIndex\n    accommodation: FoodShopIndex\n    transit: FoodShopIndex\n    picnic: FoodShopIndex\n    outdoor_furniture: FoodShopIndex\n    activity: FoodShopIndex\n    screen_pressure: WeightedPointIndex\n    places: PlaceAnchorIndex\n    adaptive_candidates: list[tuple[int, float, float]]\n'''
assert old in s
s = s.replace(old, new, 1)

old = '''    food = FoodShopIndex.empty()\n    accommodation = FoodShopIndex.empty()\n    transit = FoodShopIndex.empty()\n    activity = FoodShopIndex.empty()\n'''
new = '''    food = FoodShopIndex.empty()\n    accommodation = FoodShopIndex.empty()\n    transit = FoodShopIndex.empty()\n    picnic = FoodShopIndex.empty()\n    outdoor_furniture = FoodShopIndex.empty()\n    activity = FoodShopIndex.empty()\n'''
assert old in s
s = s.replace(old, new, 1)

old = '''        if is_transit_stop(tags):\n            transit.add(*location)\n            adaptive = True\n        if adaptive:\n'''
new = '''        if is_transit_stop(tags):\n            transit.add(*location)\n            adaptive = True\n        if is_picnic_site(tags):\n            picnic.add(*location)\n            adaptive = True\n        if is_outdoor_furniture(tags):\n            outdoor_furniture.add(*location)\n            adaptive = True\n        if adaptive:\n'''
assert old in s
s = s.replace(old, new, 1)

old = '    return ContextIndexes(food, accommodation, transit, activity, screen_pressure, places, adaptive_candidates)\n'
new = '    return ContextIndexes(food, accommodation, transit, picnic, outdoor_furniture, activity, screen_pressure, places, adaptive_candidates)\n'
assert old in s
s = s.replace(old, new, 1)

# Insert generic outdoor enrichment before activity diagnostics.
anchor = '\ndef enrich_activity_diagnostics(\n'
assert anchor in s
addition = '''\ndef enrich_outdoor_context(\n    item: object,\n    tags: Mapping[str, str] | object,\n    index: FoodShopIndex,\n    *,\n    kind: str,\n) -> tuple[dict[str, str], bool, dict[str, object] | None]:\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    result = {str(key): str(value) for key, value in items}\n    matches = is_picnic_site(result) if kind == "picnic" else is_outdoor_furniture(result)\n    if not matches:\n        return result, False, None\n    location = valid_node_location(item)\n    if location is None:\n        return result, False, None\n    lat, lon = location\n    objects_2km = index.count_within(lat, lon, 2.0)\n    objects_10km = index.count_within(lat, lon, 10.0)\n    context, priority = classify_outdoor_rarity(objects_2km=objects_2km, objects_10km=objects_10km)\n    desired = {\n        POI_CONTEXT_TAG: context,\n        POI_PRIORITY_TAG: priority,\n        f"uralla:poi_{kind}_2km": str(objects_2km),\n        f"uralla:poi_{kind}_10km": str(objects_10km),\n    }\n    changed = any(result.get(key) != value for key, value in desired.items())\n    result.update(desired)\n    return result, changed, {\n        "id": int(getattr(item, "id", 0)),\n        "name": result.get("name"),\n        "kind": kind,\n        "context": context,\n        "priority": priority,\n        "objects_2km": objects_2km,\n        "objects_10km": objects_10km,\n        "lat": lat,\n        "lon": lon,\n    }\n\n\n'''
s = s.replace(anchor, addition + anchor, 1)
p.write_text(s, encoding='utf-8')

# ---- preprocessor.py ----
p = Path('uralla_build/preprocessor.py')
s = p.read_text(encoding='utf-8')
old = '''    enrich_accommodation_context,\n    enrich_activity_diagnostics,\n    enrich_food_shop_context,\n    enrich_transit_stop_context,\n)\n'''
new = '''    enrich_accommodation_context,\n    enrich_activity_diagnostics,\n    enrich_food_shop_context,\n    enrich_outdoor_context,\n    enrich_transit_stop_context,\n)\n'''
assert old in s
s = s.replace(old, new, 1)

old = '''    transit_stop_index = context_indexes.transit\n    activity_index = context_indexes.activity\n'''
new = '''    transit_stop_index = context_indexes.transit\n    picnic_index = context_indexes.picnic\n    outdoor_furniture_index = context_indexes.outdoor_furniture\n    activity_index = context_indexes.activity\n'''
assert old in s
s = s.replace(old, new, 1)

old = '''        f"transit {transit_stop_index.shop_count:,}; "\n        f"activity {activity_index.shop_count:,}; "\n'''
new = '''        f"transit {transit_stop_index.shop_count:,}; "\n        f"picnic {picnic_index.shop_count:,}; "\n        f"furniture {outdoor_furniture_index.shop_count:,}; "\n        f"activity {activity_index.shop_count:,}; "\n'''
assert old in s
s = s.replace(old, new, 1)

anchor = '''                final_tags, activity_added, activity_sample = enrich_activity_diagnostics(\n                    item, final_tags, activity_index, place_anchor_index, activity_thresholds, screen_pressure_index, screen_thresholds\n                )\n'''
assert anchor in s
insert = '''                final_tags, picnic_added, _picnic_sample = enrich_outdoor_context(\n                    item, final_tags, picnic_index, kind="picnic"\n                )\n                if picnic_added:\n                    counters["picnic_context_enriched"] += 1\n\n                final_tags, furniture_added, _furniture_sample = enrich_outdoor_context(\n                    item, final_tags, outdoor_furniture_index, kind="furniture"\n                )\n                if furniture_added:\n                    counters["furniture_context_enriched"] += 1\n\n'''
s = s.replace(anchor, insert + anchor, 1)
p.write_text(s, encoding='utf-8')

# ---- style ----
p = Path('styles/uralla/points')
s = p.read_text(encoding='utf-8')
old = '''# Picnic sites are destination-level POIs and stay visible from 22 through 24.\n# A shelter still uses the shelter icon; ordinary picnic sites use 0x4a00.\ntourism=picnic_site & shelter=yes [0x2b05 resolution 22]\ntourism=picnic_site & shelter!=yes [0x4a00 resolution 22]\n\nleisure=firepit | amenity=firepit | amenity=bbq | tourism=picnic_site & fireplace=yes {name '${name}'} [0x2b06 resolution 24]\n# Benches and picnic tables are smaller infrastructure: visible from 23 through 24.\n(amenity=bench | leisure=picnic_table) [0x4a01 resolution 23]\n'''
new = '''# Adaptive outdoor POIs. Picnic sites use the full H/M/L range; benches and\n# picnic tables are capped at resolution 23 even when classified H.\nuralla:poi_lod_class=H & tourism=picnic_site & shelter=yes [0x2b05 resolution 22]\nuralla:poi_lod_class=M & tourism=picnic_site & shelter=yes [0x2b05 resolution 23]\nuralla:poi_lod_class=L & tourism=picnic_site & shelter=yes [0x2b05 resolution 24]\nuralla:poi_lod_class=H & tourism=picnic_site & shelter!=yes [0x4a00 resolution 22]\nuralla:poi_lod_class=M & tourism=picnic_site & shelter!=yes [0x4a00 resolution 23]\nuralla:poi_lod_class=L & tourism=picnic_site & shelter!=yes [0x4a00 resolution 24]\ntourism=picnic_site & shelter=yes [0x2b05 resolution 24]\ntourism=picnic_site & shelter!=yes [0x4a00 resolution 24]\n\nleisure=firepit | amenity=firepit | amenity=bbq | tourism=picnic_site & fireplace=yes {name '${name}'} [0x2b06 resolution 24]\nuralla:poi_lod_class=H & (amenity=bench | leisure=picnic_table) [0x4a01 resolution 23]\nuralla:poi_lod_class=M & (amenity=bench | leisure=picnic_table) [0x4a01 resolution 23]\nuralla:poi_lod_class=L & (amenity=bench | leisure=picnic_table) [0x4a01 resolution 24]\n(amenity=bench | leisure=picnic_table) [0x4a01 resolution 24]\n'''
assert old in s, 'outdoor style block not found'
p.write_text(s.replace(old, new, 1), encoding='utf-8')

# ---- tests ----
p = Path('tests/test_poi_context.py')
s = p.read_text(encoding='utf-8')
if 'classify_outdoor_rarity' not in s:
    s = s.replace('from uralla_build.poi_context import (', 'from uralla_build.poi_context import (')
    # Add imports adjacent to classify screen pressure if present.
    marker = '    classify_screen_pressure,\n'
    if marker in s:
        s = s.replace(marker, marker + '    classify_outdoor_rarity,\n    is_outdoor_furniture,\n    is_picnic_site,\n', 1)
    # append tests inside file before main guard, otherwise at end.
    tests = '''\n    def test_outdoor_candidate_detection(self):\n        self.assertTrue(is_picnic_site({"tourism": "picnic_site"}))\n        self.assertTrue(is_outdoor_furniture({"amenity": "bench"}))\n        self.assertTrue(is_outdoor_furniture({"leisure": "picnic_table"}))\n        self.assertFalse(is_outdoor_furniture({"amenity": "shelter"}))\n\n    def test_outdoor_rarity(self):\n        self.assertEqual(classify_outdoor_rarity(objects_2km=1, objects_10km=10), ("remote", "isolated"))\n        self.assertEqual(classify_outdoor_rarity(objects_2km=3, objects_10km=25), ("settlement", "sparse"))\n        self.assertEqual(classify_outdoor_rarity(objects_2km=4, objects_10km=26), ("urban", "common"))\n'''
    guard = '\n\nif __name__ == "__main__":\n'
    if guard in s:
        s = s.replace(guard, tests + guard, 1)
    else:
        s += tests
    p.write_text(s, encoding='utf-8')

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pre = ROOT / 'uralla_build' / 'preprocessor.py'
points = ROOT / 'styles' / 'uralla' / 'points'
test_pre = ROOT / 'tests' / 'test_preprocessor.py'
test_style = ROOT / 'tests' / 'test_archaeological_monument_style.py'

text = pre.read_text(encoding='utf-8')
anchor = 'PEAK_LANDMARK_TAG = "uralla:peak_landmark"\n'
insert = anchor + 'LONG_NAME_TAG = "uralla:long_name"\nLONG_NAME_LIMIT = 30\n'
assert text.count(anchor) == 1
assert 'LONG_NAME_TAG = ' not in text
text = text.replace(anchor, insert, 1)

anchor = '''def enrich_peak_landmark_tags(\n    tags: Mapping[str, str] | object,\n    landmarks: frozenset[str],\n) -> tuple[dict[str, str], bool]:\n'''
helper = '''def enrich_long_name_tags(\n    tags: Mapping[str, str] | object,\n    limit: int = LONG_NAME_LIMIT,\n) -> tuple[dict[str, str], bool]:\n    """Mark objects whose original OSM name is too long for compact Garmin labels."""\n\n    items = tags.items() if isinstance(tags, Mapping) else iter(tags)  # type: ignore[arg-type]\n    result = {str(key): str(value) for key, value in items}\n    name = result.get("name")\n    if name is None or len(name) <= limit:\n        return result, False\n    changed = result.get(LONG_NAME_TAG) != "yes"\n    result[LONG_NAME_TAG] = "yes"\n    return result, changed\n\n\n''' + anchor
assert text.count(anchor) == 1
assert 'def enrich_long_name_tags(' not in text
text = text.replace(anchor, helper, 1)

old = '''                final_tags, peak_added = enrich_peak_landmark_tags(\n                    decision.tags, peak_landmarks\n                )\n'''
new = '''                final_tags, _long_name_added = enrich_long_name_tags(decision.tags)\n                final_tags, peak_added = enrich_peak_landmark_tags(\n                    final_tags, peak_landmarks\n                )\n'''
assert text.count(old) == 1
text = text.replace(old, new, 1)
pre.write_text(text, encoding='utf-8')

text = points.read_text(encoding='utf-8')
old = '(historic=archaeological_site | historic=monument) [0x2c04 resolution 24]\n'
new = "# Long OSM names remain in source tags; only the Garmin map label becomes generic.\nhistoric=monument & uralla:long_name=yes { name 'памятник' } [0x2c04 resolution 24]\n" + old
assert text.count(old) == 1
assert 'historic=monument & uralla:long_name=yes' not in text
text = text.replace(old, new, 1)
points.write_text(text, encoding='utf-8')

text = test_pre.read_text(encoding='utf-8')
old = '    enrich_peak_landmark_tags,\n'
new = '    enrich_long_name_tags,\n' + old
assert text.count(old) == 1
text = text.replace(old, new, 1)
anchor = '    def test_peak_catalog_loads_confirmed_landmarks(self) -> None:\n'
test = '''    def test_long_name_marker_uses_strict_30_character_limit(self) -> None:\n        exact = "А" * 30\n        tags, changed = enrich_long_name_tags({"name": exact, "historic": "monument"})\n        self.assertFalse(changed)\n        self.assertNotIn("uralla:long_name", tags)\n        self.assertEqual(tags["name"], exact)\n\n        long_name = "А" * 31\n        tags, changed = enrich_long_name_tags({"name": long_name, "historic": "monument"})\n        self.assertTrue(changed)\n        self.assertEqual(tags["uralla:long_name"], "yes")\n        self.assertEqual(tags["name"], long_name)\n\n''' + anchor
assert text.count(anchor) == 1
text = text.replace(anchor, test, 1)
test_pre.write_text(text, encoding='utf-8')

text = test_style.read_text(encoding='utf-8')
anchor = '    def test_archaeological_site_and_monument_share_one_rule(self) -> None:\n'
test = '''    def test_long_monument_name_uses_generic_garmin_label(self) -> None:\n        points = POINTS.read_text(encoding='utf-8')\n        rule = "historic=monument & uralla:long_name=yes { name 'памятник' } [0x2c04 resolution 24]"\n        self.assertIn(rule, points)\n        self.assertLess(points.index(rule), points.index('(historic=archaeological_site | historic=monument) [0x2c04 resolution 24]'))\n\n''' + anchor
assert text.count(anchor) == 1
text = text.replace(anchor, test, 1)
test_style.write_text(text, encoding='utf-8')

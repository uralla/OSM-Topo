from pathlib import Path

MANIFEST = Path('config/maps.yaml')
EXTERNAL = Path('uralla_build/external_data.py')
TEST = Path('tests/test_external_data.py')

manifest = MANIFEST.read_text(encoding='utf-8')
old_ru = '    geonames: input/ru.zip\n'
old_all = '    geonames: input/allCountries.zip\n'
count_ru = manifest.count(old_ru)
count_all = manifest.count(old_all)
if count_ru + count_all == 0:
    raise SystemExit('no legacy GeoNames product paths found')
manifest = manifest.replace(old_ru, '    geonames: input/cities15000.zip\n')
manifest = manifest.replace(old_all, '    geonames: input/cities15000.zip\n')
MANIFEST.write_text(manifest, encoding='utf-8', newline='\n')

external = EXTERNAL.read_text(encoding='utf-8')
old_urls = '''SUPPLEMENTAL_URLS = {\n    "bounds": "https://www.thkukuk.de/osm/data/bounds-latest.zip",\n    "sea": "https://www.thkukuk.de/osm/data/sea-latest.zip",\n}\n'''
new_urls = '''SUPPLEMENTAL_URLS = {\n    "bounds": "https://www.thkukuk.de/osm/data/bounds-latest.zip",\n    "sea": "https://www.thkukuk.de/osm/data/sea-latest.zip",\n    "geonames": "https://download.geonames.org/export/dump/cities15000.zip",\n}\n'''
if old_urls not in external:
    raise SystemExit('supplemental URL block not found')
external = external.replace(old_urls, new_urls, 1)
old_loop = '    for name in ("bounds", "sea"):\n        value = defaults.get(name)\n'
new_loop = '''    resources = {\n        "bounds": defaults.get("bounds"),\n        "sea": defaults.get("sea"),\n        "geonames": "input/cities15000.zip",\n    }\n    for name, value in resources.items():\n'''
if old_loop not in external:
    raise SystemExit('supplemental loop not found')
external = external.replace(old_loop, new_loop, 1)
old_error = '            results.append(RefreshResult(name, "error", "", f"defaults.{name} is not configured"))\n'
new_error = '            results.append(RefreshResult(name, "error", "", f"supplemental {name} path is not configured"))\n'
external = external.replace(old_error, new_error, 1)
EXTERNAL.write_text(external, encoding='utf-8', newline='\n')

# Extend existing refresh tests without coupling them to network access.
test = TEST.read_text(encoding='utf-8')
test = test.replace("self.assertEqual(len(results), 2)", "self.assertEqual(len(results), 3)")
test = test.replace("self.assertEqual({result.name for result in results}, {'bounds', 'sea'})", "self.assertEqual({result.name for result in results}, {'bounds', 'sea', 'geonames'})")
if 'cities15000.zip' not in test:
    marker = "            self.assertTrue((host.paths.data_root / 'input/sea-latest.zip').is_file())\n"
    if marker in test:
        test = test.replace(marker, marker + "            self.assertTrue((host.paths.data_root / 'input/cities15000.zip').is_file())\n", 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

print(f'migrated GeoNames: {count_ru} ru.zip + {count_all} allCountries.zip -> cities15000.zip')

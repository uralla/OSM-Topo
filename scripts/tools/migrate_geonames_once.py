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

# Extend existing refresh tests without real network access.
test = TEST.read_text(encoding='utf-8')
failed_setup = '''            for name in ("bounds-latest.zip", "sea-latest.zip"):\n                self._zip(root / "data/input" / name, "old")\n\n            def downloader(url: str, target: Path) -> None:\n                raise OSError("offline")\n'''
failed_setup_new = '''            for name in ("bounds-latest.zip", "sea-latest.zip", "cities15000.zip"):\n                self._zip(root / "data/input" / name, "old")\n\n            def downloader(url: str, target: Path) -> None:\n                raise OSError("offline")\n'''
if failed_setup not in test:
    raise SystemExit('fallback test setup not found')
test = test.replace(failed_setup, failed_setup_new, 1)
failed_verify = '''            for name in ("bounds-latest.zip", "sea-latest.zip"):\n                with zipfile.ZipFile(root / "data/input" / name) as archive:\n                    self.assertEqual(archive.read("payload.txt"), b"old")\n'''
failed_verify_new = '''            for name in ("bounds-latest.zip", "sea-latest.zip", "cities15000.zip"):\n                with zipfile.ZipFile(root / "data/input" / name) as archive:\n                    self.assertEqual(archive.read("payload.txt"), b"old")\n'''
if failed_verify not in test:
    raise SystemExit('fallback test verification not found')
test = test.replace(failed_verify, failed_verify_new, 1)
# Successful refresh should include the third archive and preserve source provenance.
success_anchor = '''            for name in ("bounds-latest.zip", "sea-latest.zip"):\n                with zipfile.ZipFile(root / "data/input" / name) as archive:\n                    self.assertIn("https://www.thkukuk.de/", archive.read("payload.txt").decode("utf-8"))\n'''
success_new = success_anchor + '''            with zipfile.ZipFile(root / "data/input/cities15000.zip") as archive:\n                self.assertIn("https://download.geonames.org/", archive.read("payload.txt").decode("utf-8"))\n'''
if success_anchor not in test:
    raise SystemExit('successful refresh test anchor not found')
test = test.replace(success_anchor, success_new, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

print(f'migrated GeoNames: {count_ru} ru.zip + {count_all} allCountries.zip -> cities15000.zip')

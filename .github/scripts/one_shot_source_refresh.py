from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match, got {count}"
    return text.replace(old, new, 1)

# --- external_data.py: refresh primary OSM PBF sources on demand ---
p = Path('uralla_build/external_data.py')
s = p.read_text(encoding='utf-8')
marker = '''SUPPLEMENTAL_URLS = {
    "bounds": "https://www.thkukuk.de/osm/data/bounds-latest.zip",
    "sea": "https://www.thkukuk.de/osm/data/sea-latest.zip",
    "geonames": "https://download.geonames.org/export/dump/cities15000.zip",
}
'''
addition = marker + '''\nOSM_SOURCE_URLS = {
    "russia": "https://download.geofabrik.de/russia-latest.osm.pbf",
    "northwestern": "https://download.geofabrik.de/russia/northwestern-fed-district-latest.osm.pbf",
    "crimea": "https://download.geofabrik.de/russia/crimean-fed-district-latest.osm.pbf",
    "belarus": "https://download.geofabrik.de/europe/belarus-latest.osm.pbf",
    "georgia": "https://download.geofabrik.de/europe/georgia-latest.osm.pbf",
    "turkey": "https://download.geofabrik.de/europe/turkey-latest.osm.pbf",
    "kazakhstan": "https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf",
    "kyrgyzstan": "https://download.geofabrik.de/asia/kyrgyzstan-latest.osm.pbf",
    "armenia": "https://download.geofabrik.de/asia/armenia-latest.osm.pbf",
    "mongolia": "https://download.geofabrik.de/asia/mongolia-latest.osm.pbf",
}
'''
s = replace_once(s, marker, addition, 'source URL table')
insert = '''\ndef refresh_osm_source(
    manifest: dict[str, object],
    host: HostConfig,
    source_key: str,
    *,
    downloader: Callable[[str, Path], None] | None = None,
    reporter: Callable[[str], None] | None = None,
) -> RefreshResult:
    """Ensure one primary Geofabrik PBF exists and is current enough for a build.

    A new file is staged and atomically installed. If refresh fails but an older
    local PBF exists, keep it and continue with a warning; if no fallback exists,
    fail before the build pipeline starts.
    """
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        return RefreshResult(source_key, "error", "", "manifest sources are missing")
    source = sources.get(source_key)
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        return RefreshResult(source_key, "error", "", f"source {source_key!r} is not configured")
    url = OSM_SOURCE_URLS.get(source_key)
    if url is None:
        return RefreshResult(source_key, "error", "", f"no download URL configured for source {source_key!r}")

    target = data_path(host, source["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if reporter is not None:
        if target.is_file():
            reporter(f"[source:{source_key}] local: {target} ({_format_mib(target.stat().st_size)})")
        else:
            reporter(f"[source:{source_key}] local: missing ({target})")

    metadata: RemoteMetadata | None = None
    if downloader is None and target.is_file():
        try:
            if reporter is not None:
                reporter(f"[source:{source_key}] checking remote metadata: {url}")
            metadata = _remote_metadata(url)
            if _is_current(target, metadata):
                size = target.stat().st_size
                if reporter is not None:
                    reporter(f"[source:{source_key}] up to date: {_format_mib(size)}; skipping download")
                return RefreshResult(source_key, "unchanged", str(target), "remote file is not newer", size)
        except Exception as exc:
            if reporter is not None:
                reporter(f"[source:{source_key}] metadata check unavailable: {exc}; downloading normally")

    try:
        with tempfile.TemporaryDirectory(prefix=f".uralla-source-{source_key}-", dir=target.parent) as temp_dir:
            staged = Path(temp_dir) / target.name
            if reporter is not None:
                reporter(f"[source:{source_key}] download: {url}")
            if downloader is None:
                def progress(downloaded: int, total: int | None, elapsed: float) -> None:
                    if reporter is None:
                        return
                    if downloaded == 0:
                        reporter(f"[source:{source_key}] receiving: " + (f"0.0 / {_format_mib(total)}" if total else "size unknown"))
                        return
                    speed = downloaded / max(elapsed, 1e-9)
                    if total:
                        reporter(f"[source:{source_key}] received: {_format_mib(downloaded)} / {_format_mib(total)} ({min(100.0, downloaded * 100 / total):.1f}%) at {_format_mib(int(speed))}/s")
                    else:
                        reporter(f"[source:{source_key}] received: {_format_mib(downloaded)} at {_format_mib(int(speed))}/s")
                _download(url, staged, progress=progress)
            else:
                downloader(url, staged)
            size = staged.stat().st_size
            if size <= 0:
                raise OSError("downloaded PBF is empty")
            replacement = target.parent / f".{target.name}.partial"
            if replacement.exists():
                replacement.unlink()
            staged.replace(replacement)
            os.replace(replacement, target)
            if metadata is not None and metadata.modified_at is not None:
                os.utime(target, (metadata.modified_at, metadata.modified_at))
        if reporter is not None:
            reporter(f"[source:{source_key}] updated: {target} ({_format_mib(size)})")
        return RefreshResult(source_key, "updated", str(target), url, size)
    except Exception as exc:
        if target.is_file() and target.stat().st_size > 0:
            if reporter is not None:
                reporter(f"[source:{source_key}] WARN: refresh failed; keeping existing PBF: {exc}")
            return RefreshResult(source_key, "warning", str(target), f"refresh failed; keeping existing PBF: {exc}", target.stat().st_size)
        if reporter is not None:
            reporter(f"[source:{source_key}] ERROR: refresh failed and no local fallback exists: {exc}")
        return RefreshResult(source_key, "error", str(target), f"refresh failed and no local fallback exists: {exc}")
\n'''
needle = '\ndef has_refresh_errors(results: list[RefreshResult]) -> bool:\n'
assert s.count(needle) == 1
s = s.replace(needle, insert + needle, 1)
p.write_text(s, encoding='utf-8')

# --- cli.py: refresh the source before a real full build ---
p = Path('uralla_build/cli.py')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    'from .external_data import has_refresh_errors, refresh_supplemental_data\n',
    'from .external_data import has_refresh_errors, refresh_osm_source, refresh_supplemental_data\n',
    'cli import',
)
old = '''        product = products[args.product]\n\n        if not args.apply:\n'''
new = '''        product = products[args.product]\n\n        if args.apply and getattr(args, "from_stage", None) != "mkgmap":\n            source_key = product.get("source")\n            if not isinstance(source_key, str):\n                raise StageError(f"product {args.product!r} has no source")\n            if not args.json:\n                print(f"Checking OSM source for {args.product}: {source_key}")\n            source_result = refresh_osm_source(\n                manifest, host, source_key, reporter=None if args.json else print\n            )\n            if source_result.status == "error":\n                raise StageError(source_result.detail)\n\n        if not args.apply:\n'''
s = replace_once(s, old, new, 'build source refresh')
p.write_text(s, encoding='utf-8')

# --- maps.yaml: all products that already use complete Geofabrik extracts skip extract ---
p = Path('config/maps.yaml')
s = p.read_text(encoding='utf-8')
for product, source in (
    ('armenia', 'armenia'),
    ('belarus', 'belarus'),
    ('georgia', 'georgia'),
    ('kg', 'kyrgyzstan'),
    ('mongolia', 'mongolia'),
    ('turkey', 'turkey'),
):
    old = f"  {product}:\n    source: {source}\n"
    new = f"  {product}:\n    source: {source}\n    extract: false\n"
    s = replace_once(s, old, new, f'{product} extract flag')
for product in ('crimea', 'kz', 'northwestern-fed-district'):
    assert re.search(rf'^  {re.escape(product)}:\n    source: .*\n    extract: false$', s, re.M), product
p.write_text(s, encoding='utf-8')

# --- tests ---
p = Path('tests/test_external_data.py')
s = p.read_text(encoding='utf-8')
s = s.replace(
    '    RemoteMetadata,\n',
    '    OSM_SOURCE_URLS,\n    RemoteMetadata,\n',
    1,
)
s = s.replace(
    '    refresh_supplemental_data,\n',
    '    refresh_osm_source,\n    refresh_supplemental_data,\n',
    1,
)
append = '''\n\n    def test_primary_source_downloads_to_manifest_path(self) -> None:\n        with TemporaryDirectory() as directory:\n            root = Path(directory)\n            manifest = {"sources": {"kazakhstan": {"path": "input/kazakhstan-latest.osm.pbf"}}}\n            def downloader(url: str, target: Path) -> None:\n                self.assertEqual(url, OSM_SOURCE_URLS["kazakhstan"])\n                target.write_bytes(b"pbf-test")\n            result = refresh_osm_source(manifest, self._host(root), "kazakhstan", downloader=downloader)\n            self.assertEqual(result.status, "updated")\n            self.assertEqual((root / "data/input/kazakhstan-latest.osm.pbf").read_bytes(), b"pbf-test")\n\n    def test_primary_source_failure_without_local_file_is_error(self) -> None:\n        with TemporaryDirectory() as directory:\n            root = Path(directory)\n            manifest = {"sources": {"armenia": {"path": "input/armenia-latest.osm.pbf"}}}\n            result = refresh_osm_source(\n                manifest, self._host(root), "armenia",\n                downloader=lambda _url, _target: (_ for _ in ()).throw(OSError("offline")),\n            )\n            self.assertEqual(result.status, "error")\n'''
assert '\n\nif __name__ == "__main__":\n' in s
s = s.replace('\n\nif __name__ == "__main__":\n', append + '\n\nif __name__ == "__main__":\n', 1)
p.write_text(s, encoding='utf-8')

Path('tests/test_source_extract_policy.py').write_text('''from pathlib import Path\nimport yaml\n\nROOT = Path(__file__).resolve().parents[1]\n\ndef test_complete_geofabrik_products_skip_extract():\n    manifest = yaml.safe_load((ROOT / "config/maps.yaml").read_text(encoding="utf-8"))\n    products = manifest["products"]\n    expected = {\n        "armenia": "armenia", "belarus": "belarus", "crimea": "crimea",\n        "georgia": "georgia", "kg": "kyrgyzstan", "kz": "kazakhstan",\n        "mongolia": "mongolia", "northwestern-fed-district": "northwestern",\n        "turkey": "turkey",\n    }\n    for product, source in expected.items():\n        assert products[product]["source"] == source\n        assert products[product].get("extract") is False\n\ndef test_all_manifest_sources_have_download_urls():\n    from uralla_build.external_data import OSM_SOURCE_URLS\n    manifest = yaml.safe_load((ROOT / "config/maps.yaml").read_text(encoding="utf-8"))\n    assert set(manifest["sources"]) == set(OSM_SOURCE_URLS)\n''', encoding='utf-8')

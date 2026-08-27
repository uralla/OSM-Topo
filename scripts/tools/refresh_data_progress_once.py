from pathlib import Path

EXTERNAL = Path('uralla_build/external_data.py')
CLI = Path('uralla_build/cli.py')
TEST = Path('tests/test_external_data.py')

external = EXTERNAL.read_text(encoding='utf-8')
external = external.replace('from typing import Callable\n', 'from typing import Callable\n')
old_sig = '''def refresh_supplemental_data(\n    manifest: dict[str, object],\n    host: HostConfig,\n    *,\n    downloader: Callable[[str, Path], None] = _download,\n) -> list[RefreshResult]:\n'''
new_sig = '''def refresh_supplemental_data(\n    manifest: dict[str, object],\n    host: HostConfig,\n    *,\n    downloader: Callable[[str, Path], None] = _download,\n    reporter: Callable[[str], None] | None = None,\n) -> list[RefreshResult]:\n'''
if old_sig not in external:
    raise SystemExit('external signature anchor not found')
external = external.replace(old_sig, new_sig, 1)
old_target = '''        target = data_path(host, value)\n        target.parent.mkdir(parents=True, exist_ok=True)\n        url = SUPPLEMENTAL_URLS[name]\n        try:\n'''
new_target = '''        target = data_path(host, value)\n        target.parent.mkdir(parents=True, exist_ok=True)\n        url = SUPPLEMENTAL_URLS[name]\n        if reporter is not None:\n            if target.is_file():\n                reporter(f"[{name}] local: {target} ({target.stat().st_size} bytes)")\n            else:\n                reporter(f"[{name}] local: missing ({target})")\n            reporter(f"[{name}] download: {url}")\n        try:\n'''
if old_target not in external:
    raise SystemExit('external target anchor not found')
external = external.replace(old_target, new_target, 1)
old_validate = '''                downloader(url, staged)\n                _validate_zip(staged)\n                size = staged.stat().st_size\n'''
new_validate = '''                downloader(url, staged)\n                if reporter is not None:\n                    reporter(f"[{name}] downloaded: {staged.stat().st_size} bytes; validating ZIP")\n                _validate_zip(staged)\n                size = staged.stat().st_size\n'''
external = external.replace(old_validate, new_validate, 1)
old_success = '''            results.append(RefreshResult(name, "updated", str(target), url, size))\n'''
new_success = '''            if reporter is not None:\n                reporter(f"[{name}] updated: {target} ({size} bytes)")\n            results.append(RefreshResult(name, "updated", str(target), url, size))\n'''
external = external.replace(old_success, new_success, 1)
old_warning = '''            if target.is_file():\n                results.append(\n'''
new_warning = '''            if target.is_file():\n                if reporter is not None:\n                    reporter(f"[{name}] WARN: refresh failed; keeping existing archive: {exc}")\n                results.append(\n'''
external = external.replace(old_warning, new_warning, 1)
old_error = '''            else:\n                results.append(\n                    RefreshResult(\n                        name,\n                        "error",\n'''
new_error = '''            else:\n                if reporter is not None:\n                    reporter(f"[{name}] ERROR: refresh failed and no local fallback exists: {exc}")\n                results.append(\n                    RefreshResult(\n                        name,\n                        "error",\n'''
external = external.replace(old_error, new_error, 1)
EXTERNAL.write_text(external, encoding='utf-8', newline='\n')

cli = CLI.read_text(encoding='utf-8')
old_call = '        results = refresh_supplemental_data(manifest, host)\n'
new_call = '''        if not args.json:\n            print("Refreshing supplemental map data...")\n            print(f"Data root: {host.paths.data_root}")\n            print()\n        results = refresh_supplemental_data(\n            manifest,\n            host,\n            reporter=None if args.json else print,\n        )\n'''
if old_call not in cli:
    raise SystemExit('CLI refresh call anchor not found')
cli = cli.replace(old_call, new_call, 1)
old_else = '''    else:\n        for result in results:\n            print(f"{result.status.upper():7} {result.name}: {result.target} — {result.detail}")\n    return 1 if has_refresh_errors(results) else 0\n'''
new_else = '''    else:\n        print()\n        print("Refresh summary")\n        print("-" * 72)\n        for result in results:\n            size = f" ({result.size} bytes)" if result.size is not None else ""\n            print(f"{result.status.upper():7} {result.name:<10} {result.target}{size}")\n            if result.status != "updated":\n                print(f"        {result.detail}")\n        print("-" * 72)\n        updated = sum(result.status == "updated" for result in results)\n        warnings = sum(result.status == "warning" for result in results)\n        errors = sum(result.status == "error" for result in results)\n        print(f"Updated: {updated}  Warnings: {warnings}  Errors: {errors}")\n    return 1 if has_refresh_errors(results) else 0\n'''
if old_else not in cli:
    raise SystemExit('CLI output anchor not found')
cli = cli.replace(old_else, new_else, 1)
CLI.write_text(cli, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor = '''    def test_failed_refresh_without_fallback_is_error(self) -> None:\n'''
insert = '''    def test_reporter_receives_progress_messages(self) -> None:\n        with TemporaryDirectory() as directory:\n            root = Path(directory)\n            messages: list[str] = []\n\n            def downloader(url: str, target: Path) -> None:\n                self._zip(target, url)\n\n            results = refresh_supplemental_data(\n                self._manifest(),\n                self._host(root),\n                downloader=downloader,\n                reporter=messages.append,\n            )\n            self.assertFalse(has_refresh_errors(results))\n            joined = "\\n".join(messages)\n            self.assertIn("[bounds] local: missing", joined)\n            self.assertIn("[bounds] download:", joined)\n            self.assertIn("validating ZIP", joined)\n            self.assertIn("[geonames] updated:", joined)\n\n'''
if 'test_reporter_receives_progress_messages' not in test:
    if anchor not in test:
        raise SystemExit('test anchor not found')
    test = test.replace(anchor, insert + anchor, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

print('added refresh-data live progress and summary')

from pathlib import Path

DOCTOR = Path('uralla_build/doctor.py')
TEST = Path('tests/test_doctor.py')

doctor = DOCTOR.read_text(encoding='utf-8')
old = '''        external_paths: set[str] = set()\n        for key in ("bounds", "sea"):\n            value = defaults.get(key)\n            if isinstance(value, str):\n                external_paths.add(value)\n        for source in manifest.get("sources", {}).values():\n            if isinstance(source, dict) and isinstance(source.get("path"), str):\n                external_paths.add(source["path"])\n        for product in manifest.get("products", {}).values():\n            if not isinstance(product, dict):\n                continue\n            for key in ("polygon", "elevation", "geonames"):\n                value = product.get(key)\n                if isinstance(value, str):\n                    external_paths.add(value)\n        for value in sorted(external_paths):\n            path = data_path(host, value)\n            checks.append(_check(f"data:{value}", path.is_file(), str(path)))\n'''
new = '''        external_paths: set[str] = set()\n        source_pbf_paths: set[str] = set()\n        for key in ("bounds", "sea"):\n            value = defaults.get(key)\n            if isinstance(value, str):\n                external_paths.add(value)\n        for source in manifest.get("sources", {}).values():\n            if isinstance(source, dict) and isinstance(source.get("path"), str):\n                source_path = source["path"]\n                if source_path.lower().endswith(".pbf"):\n                    source_pbf_paths.add(source_path)\n                else:\n                    external_paths.add(source_path)\n        for product in manifest.get("products", {}).values():\n            if not isinstance(product, dict):\n                continue\n            for key in ("polygon", "elevation", "geonames"):\n                value = product.get(key)\n                if isinstance(value, str):\n                    external_paths.add(value)\n        for value in sorted(external_paths):\n            path = data_path(host, value)\n            checks.append(_check(f"data:{value}", path.is_file(), str(path)))\n        for value in sorted(source_pbf_paths):\n            path = data_path(host, value)\n            checks.append(_check(f"data:{value}", path.is_file(), str(path), failure="warning"))\n'''
if old not in doctor:
    raise SystemExit('doctor external-data block not found')
doctor = doctor.replace(old, new, 1)
DOCTOR.write_text(doctor, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
insert = '''    def test_missing_source_pbf_is_a_warning(self) -> None:\n        with TemporaryDirectory() as directory:\n            root = Path(directory)\n            lock = self._prepare(root)\n            (root / "data/input/source.osm.pbf").unlink()\n            checks = run_doctor(\n                _manifest(),\n                self._host(root),\n                root,\n                lock,\n                check_commands=False,\n                check_external_data=True,\n                probe_publish=False,\n            )\n            self.assertFalse(has_errors(checks), [check for check in checks if check.status == "error"])\n            self.assertTrue(\n                any(\n                    check.name == "data:input/source.osm.pbf" and check.status == "warning"\n                    for check in checks\n                )\n            )\n\n'''
anchor = '    def test_missing_external_file_is_an_error(self) -> None:\n'
if 'def test_missing_source_pbf_is_a_warning' not in test:
    if anchor not in test:
        raise SystemExit('test insertion anchor not found')
    test = test.replace(anchor, insert + anchor, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

print('doctor: missing downloadable source PBF files are warnings')

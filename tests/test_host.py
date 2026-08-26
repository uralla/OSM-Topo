from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uralla_build.host import load_host_config, resolve_host_config_path, validate_host_config


def _write_host(path: Path, root: Path, *, split_zip_volumes: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""schema_version: 1
paths:
  data_root: {root}/data
  work_root: {root}/work
  publish_root: {root}/publish
  tools_root: {root}/tools
  dem_root: {root}/dem
publication:
  img_subdir: .
  gmapi_subdir: mapsource
  img_archive: false
  gmapi_zip_mode: store
  split_zip_volumes: {'true' if split_zip_volumes else 'false'}
resources:
  product_concurrency: 1
  minimum_free_gib: 0
""",
        encoding="utf-8",
    )


class HostConfigTests(unittest.TestCase):
    def test_environment_roots_are_expanded(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "host.yaml"
            config.write_text(
                """schema_version: 1
paths:
  data_root: ${URALLA_TEST_ROOT}/data
  work_root: ${URALLA_TEST_ROOT}/work
  publish_root: ${URALLA_TEST_ROOT}/publish
  tools_root: tools
  dem_root: ${URALLA_TEST_ROOT}/dem
publication:
  img_subdir: .
  gmapi_subdir: mapsource
  img_archive: false
  gmapi_zip_mode: store
  split_zip_volumes: false
resources:
  product_concurrency: 1
  minimum_free_gib: 0
""",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"URALLA_TEST_ROOT": str(root)}):
                host = load_host_config(config, root)
            self.assertEqual(host.paths.data_root, root / "data")
            self.assertEqual(host.paths.tools_root, root / "tools")
            self.assertEqual(validate_host_config(host), [])

    def test_default_host_uses_external_pointer(self) -> None:
        with TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            workspace = Path(directory) / "workspace"
            repo.mkdir()
            config = workspace / "host.yaml"
            _write_host(config, workspace)
            (repo / ".uralla-host").write_text(f"{config}\n", encoding="utf-8")

            resolved = resolve_host_config_path(Path("config/host.yaml"), repo)
            self.assertEqual(resolved, config)

            host = load_host_config(Path("config/host.yaml"), repo)
            self.assertEqual(host.paths.data_root, workspace / "data")
            self.assertEqual(host.paths.tools_root, workspace / "tools")

    def test_host_pointer_wins_over_legacy_default_file(self) -> None:
        with TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            workspace = Path(directory) / "workspace"
            legacy_root = Path(directory) / "legacy"
            repo.mkdir()
            external = workspace / "host.yaml"
            legacy = repo / "config" / "host.yaml"
            _write_host(external, workspace)
            _write_host(legacy, legacy_root)
            (repo / ".uralla-host").write_text(f"{external}\n", encoding="utf-8")

            host = load_host_config(Path("config/host.yaml"), repo)
            self.assertEqual(host.paths.data_root, workspace / "data")

    def test_explicit_host_path_ignores_pointer(self) -> None:
        with TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            workspace = Path(directory) / "workspace"
            explicit_root = Path(directory) / "explicit"
            repo.mkdir()
            pointer_config = workspace / "host.yaml"
            explicit_config = explicit_root / "host.yaml"
            _write_host(pointer_config, workspace)
            _write_host(explicit_config, explicit_root)
            (repo / ".uralla-host").write_text(f"{pointer_config}\n", encoding="utf-8")

            host = load_host_config(explicit_config, repo)
            self.assertEqual(host.paths.data_root, explicit_root / "data")

    def test_split_zip_policy_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "host.yaml"
            _write_host(config, root, split_zip_volumes=True)
            host = load_host_config(config, root)
            self.assertTrue(
                any("split_zip_volumes" in issue.location for issue in validate_host_config(host))
            )


if __name__ == "__main__":
    unittest.main()


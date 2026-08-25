from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uralla_build.host import load_host_config, validate_host_config


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

    def test_split_zip_policy_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "host.yaml"
            config.write_text(
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
  split_zip_volumes: true
resources:
  product_concurrency: 1
  minimum_free_gib: 0
""",
                encoding="utf-8",
            )
            host = load_host_config(config, root)
            self.assertTrue(
                any("split_zip_volumes" in issue.location for issue in validate_host_config(host))
            )


if __name__ == "__main__":
    unittest.main()


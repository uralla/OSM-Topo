from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from uralla_build.manifest import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def test_project_manifest_is_valid(self) -> None:
        manifest = load_manifest(ROOT / "config" / "maps.yaml")
        self.assertEqual(len(manifest["products"]), 27)
        self.assertEqual(validate_manifest(manifest), [])

    def test_overlap_is_rejected(self) -> None:
        manifest = load_manifest(ROOT / "config" / "maps.yaml")
        broken = deepcopy(manifest)
        broken["products"]["zap-sib"]["identity"].update(
            overview_mapnumber="01010999",
            first_tile_mapid="01011000",
        )
        issues = validate_manifest(broken)
        self.assertTrue(any("overlaps" in issue.message for issue in issues))

    def test_unquoted_map_id_is_rejected(self) -> None:
        manifest = load_manifest(ROOT / "config" / "maps.yaml")
        broken = deepcopy(manifest)
        broken["products"]["ural-n"]["identity"]["first_tile_mapid"] = 1018001
        issues = validate_manifest(broken)
        self.assertTrue(any("quoted eight-digit" in issue.message for issue in issues))


if __name__ == "__main__":
    unittest.main()

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

    def test_invalid_execution_overrides_are_rejected(self) -> None:
        manifest = load_manifest(ROOT / "config/maps.yaml")
        product = manifest["products"]["ural-n"]
        product["extract"] = "yes"
        product["splitter"]["max_threads"] = True
        product["mkgmap"]["dem_dists"] = 0
        product["mkgmap"]["dem_poly"] = "yes"

        issues = validate_manifest(manifest)
        locations = {issue.location for issue in issues}
        self.assertIn("products.ural-n.extract", locations)
        self.assertIn("products.ural-n.splitter.max_threads", locations)
        self.assertIn("products.ural-n.mkgmap.dem_dists", locations)
        self.assertIn("products.ural-n.mkgmap.dem_poly", locations)

    def test_unsafe_or_duplicate_publication_names_are_rejected(self) -> None:
        manifest = load_manifest(ROOT / "config/maps.yaml")
        manifest["products"]["armenia"]["names"]["family"] = "../Armenia"
        manifest["products"]["belarus"]["names"]["output_img"] = "Armenia.OSM.IMG"

        issues = validate_manifest(manifest)
        locations = {issue.location for issue in issues}
        self.assertIn("products.armenia.names.family", locations)
        self.assertIn("products.belarus.names.output_img", locations)

    def test_invalid_preprocessor_scope_is_rejected(self) -> None:
        manifest = load_manifest(ROOT / "config/maps.yaml")
        manifest["defaults"]["preprocessor"]["blacklist"] = "/absolute.yaml"
        manifest["defaults"]["preprocessor"]["source_profiles"]["unknown"] = []

        issues = validate_manifest(manifest)
        locations = {issue.location for issue in issues}
        self.assertIn("defaults.preprocessor.blacklist", locations)
        self.assertIn("defaults.preprocessor.source_profiles.unknown", locations)


if __name__ == "__main__":
    unittest.main()

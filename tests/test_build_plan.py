from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.bootstrap import load_tools_lock
from uralla_build.build_plan import plan_product_build
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy
from uralla_build.manifest import load_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _host(root: Path) -> HostConfig:
    return HostConfig(
        HostPaths(
            root / "data",
            root / "work",
            root / "tools",
            root / "tools",
            root / "dem",
        ),
        PublicationPolicy(".", "mapsource", False, "store", False),
        1,
        0,
    )


class ProductBuildPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(PROJECT_ROOT / "config/maps.yaml")
        self.lock = load_tools_lock(PROJECT_ROOT / "config/tools.lock.yaml")

    def _plan(self, root: Path, product: str, manifest=None):
        return plan_product_build(
            manifest or self.manifest,
            _host(root),
            self.lock,
            product_key=product,
            build_id="build-1",
            repo_root=root / "repo",
            manifest_path=PROJECT_ROOT / "config/maps.yaml",
            build_date=date(2026, 8, 25),
        )

    def test_ural_plan_preserves_identity_dem_and_stage_order(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = self._plan(root, "ural-n")

            self.assertEqual(
                [stage.name for stage in plan.stages],
                [
                    "extract",
                    "transform",
                    "preprocess",
                    "merge",
                    "splitter",
                    "validate-areas",
                    "mkgmap",
                ],
            )
            splitter = next(stage for stage in plan.stages if stage.name == "splitter")
            self.assertIn("--mapid=01018001", splitter.command)
            self.assertIn("--max-nodes=2000000", splitter.command)
            self.assertEqual(splitter.prepare_directories, ("tiles",))
            mkgmap = next(stage for stage in plan.stages if stage.name == "mkgmap")
            self.assertIn("--family-id=1018", mkgmap.command)
            self.assertIn("--product-id=1", mkgmap.command)
            self.assertIn("--overview-mapnumber=01018000", mkgmap.command)
            self.assertIn("--dem-dists=9942", mkgmap.command)
            self.assertIn(
                f"--dem-poly={(root / 'repo/poly/ru_ural_polar.poly').resolve()}",
                mkgmap.command,
            )
            self.assertIn(f"--dem={root / 'dem'}", mkgmap.command)
            self.assertIn("--description=Topo-Ural-N (2026-08-25)", mkgmap.command)
            self.assertTrue(mkgmap.command[-1].endswith("/repo/styles/uralla.txt"))
            self.assertEqual(mkgmap.prepare_directories, ("garmin",))
            self.assertTrue(plan.img_source.endswith("/mkgmap/garmin/gmapsupp.img"))
            self.assertTrue(plan.gmapi_source.endswith("/mkgmap/garmin/Topo-Ural-N.gmap"))

    def test_optional_extract_and_elevation_stages_follow_manifest(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            northwestern = self._plan(root, "northwestern-fed-district")
            belarus = self._plan(root, "belarus")

            self.assertNotIn("extract", [stage.name for stage in northwestern.stages])
            self.assertIn("preprocess", [stage.name for stage in northwestern.stages])
            self.assertIn("merge", [stage.name for stage in northwestern.stages])
            self.assertIn("extract", [stage.name for stage in belarus.stages])
            self.assertIn("preprocess", [stage.name for stage in belarus.stages])
            self.assertNotIn("merge", [stage.name for stage in belarus.stages])

    def test_existing_managed_areas_are_reused(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stable = root / "repo/build-state/areas/ural-n/areas.list"
            stable.parent.mkdir(parents=True)
            stable.write_text("dummy", encoding="utf-8")

            plan = self._plan(root, "ural-n")

            splitter = next(stage for stage in plan.stages if stage.name == "splitter")
            self.assertIn(f"--split-file={stable}", splitter.command)
            self.assertEqual(plan.stable_areas, str(stable))

    def test_plan_is_shell_free_and_enriches_non_russian_products(self) -> None:
        with TemporaryDirectory() as directory:
            plan = self._plan(Path(directory), "armenia")
            payload = plan.to_dict()

            self.assertTrue(all(isinstance(stage.command, tuple) for stage in plan.stages))
            self.assertNotIn("*.pbf", " ".join(
                argument for stage in plan.stages for argument in stage.command
            ))
            preprocess = next(stage for stage in plan.stages if stage.name == "preprocess")
            self.assertIn("landmarks", preprocess.command)
            self.assertNotIn("ru-political-parties", preprocess.command)
            self.assertIn("static peak + river landmarks", payload["warnings"][0])

    def test_russian_blacklist_runs_with_landmarks_before_elevation_merge(self) -> None:
        with TemporaryDirectory() as directory:
            plan = self._plan(Path(directory), "ural-n")
            preprocess = next(stage for stage in plan.stages if stage.name == "preprocess")
            merge = next(stage for stage in plan.stages if stage.name == "merge")

            self.assertIn("landmarks", preprocess.command)
            self.assertIn("ru-political-parties", preprocess.command)
            self.assertTrue(any("preprocessed.osm.pbf" in value for value in merge.command))
            self.assertLess(
                [stage.name for stage in plan.stages].index("preprocess"),
                [stage.name for stage in plan.stages].index("merge"),
            )

    def test_new_product_cut_from_russia_automatically_gets_blacklist(self) -> None:
        with TemporaryDirectory() as directory:
            manifest = deepcopy(self.manifest)
            product = deepcopy(manifest["products"]["ural-n"])
            product["polygon"] = "poly/competition-area.poly"
            product["identity"] = {
                "family_id": 65000,
                "product_id": 1,
                "overview_mapnumber": "65000000",
                "first_tile_mapid": "65000001",
                "last_reserved_mapid": "65000999",
            }
            product["names"] = {
                "family": "Competition",
                "series": "Competition",
                "overview": "Competition",
                "description": "Competition",
                "output_img": "Competition.img",
            }
            product["source"] = "russia"
            manifest["products"]["competition-area"] = product

            plan = self._plan(Path(directory), "competition-area", manifest)
            preprocess = next(stage for stage in plan.stages if stage.name == "preprocess")

            self.assertIn("landmarks", preprocess.command)
            self.assertIn("ru-political-parties", preprocess.command)

    def test_blacklist_scope_includes_crimea_and_excludes_foreign_sources(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            crimea = self._plan(root, "crimea")
            belarus = self._plan(root, "belarus")
            armenia = self._plan(root, "armenia")

            crimea_preprocess = next(stage for stage in crimea.stages if stage.name == "preprocess")
            belarus_preprocess = next(stage for stage in belarus.stages if stage.name == "preprocess")
            armenia_preprocess = next(stage for stage in armenia.stages if stage.name == "preprocess")

            self.assertIn("ru-political-parties", crimea_preprocess.command)
            self.assertNotIn("ru-political-parties", belarus_preprocess.command)
            self.assertNotIn("ru-political-parties", armenia_preprocess.command)

    def test_every_manifest_product_has_a_complete_plan(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plans = {
                product: self._plan(root, product)
                for product in self.manifest["products"]
            }

            self.assertEqual(len(plans), 27)
            for product, plan in plans.items():
                self.assertIn("preprocess", [stage.name for stage in plan.stages], product)
                self.assertEqual(plan.stages[-2].name, "validate-areas", product)
                self.assertEqual(plan.stages[-1].name, "mkgmap", product)
                self.assertTrue(plan.img_source.endswith("gmapsupp.img"), product)
                self.assertTrue(plan.gmapi_source.endswith(".gmap"), product)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

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


class SingleDemProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(PROJECT_ROOT / "config/maps.yaml")
        self.lock = load_tools_lock(PROJECT_ROOT / "config/tools.lock.yaml")

    def test_only_one_mkgmap_args_profile_is_kept(self) -> None:
        profiles = sorted(path.name for path in (PROJECT_ROOT / "styles").glob("*.args"))
        self.assertEqual(profiles, ["uralla.args"])
        self.assertEqual(self.manifest["defaults"]["mkgmap_args"], "styles/uralla.args")

    def test_every_product_uses_shared_dem_profile(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            expected_args = str((root / "repo/styles/uralla.args").resolve())
            expected_dem = f"--dem={root / 'dem'}"

            for product in self.manifest["products"]:
                with self.subTest(product=product):
                    plan = plan_product_build(
                        self.manifest,
                        _host(root),
                        self.lock,
                        product_key=product,
                        build_id="build-1",
                        repo_root=root / "repo",
                        manifest_path=PROJECT_ROOT / "config/maps.yaml",
                        build_date=date(2026, 9, 7),
                    )
                    mkgmap = next(stage for stage in plan.stages if stage.name == "mkgmap")
                    config_index = mkgmap.command.index("-c")
                    self.assertEqual(mkgmap.command[config_index + 1], expected_args)
                    self.assertIn(expected_dem, mkgmap.command)
                    self.assertNotIn("no-dem", " ".join(mkgmap.command).lower())


if __name__ == "__main__":
    unittest.main()

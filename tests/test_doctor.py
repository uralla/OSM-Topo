from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.doctor import has_errors, run_doctor
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy


def _touch(path: Path, content: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "defaults": {
            "style": "styles/uralla",
            "typ": "styles/uralla.typ",
            "mkgmap_args": "styles/uralla.args",
            "transform_places": "scripts/transform_places.xml",
            "bounds": "input/bounds.zip",
            "sea": "input/sea.zip",
        },
        "sources": {"source": {"path": "input/source.osm.pbf"}},
        "products": {
            "test": {
                "source": "source",
                "polygon": "poly/test.poly",
                "elevation": "elevation/test.osm.pbf",
                "geonames": "input/geonames.zip",
                "identity": {
                    "family_id": 1000,
                    "product_id": 1,
                    "overview_mapnumber": "10000000",
                    "first_tile_mapid": "10000001",
                    "last_reserved_mapid": "10009999",
                },
                "names": {
                    "family": "Test",
                    "series": "Test",
                    "overview": "Test",
                    "description": "Test",
                    "output_img": "Test.img",
                },
                "splitter": {"max_nodes": 1000000},
            }
        },
    }


class DoctorTests(unittest.TestCase):
    def _host(self, root: Path) -> HostConfig:
        return HostConfig(
            HostPaths(
                data_root=root / "data",
                work_root=root / "work",
                publish_root=root / "publish",
                tools_root=root / "tools",
                dem_root=root / "data" / "dem",
            ),
            PublicationPolicy(".", "mapsource", False, "store", False),
            product_concurrency=1,
            minimum_free_gib=0,
        )

    def _prepare(self, root: Path) -> Path:
        for path in (
            "styles/uralla/info",
            "styles/uralla.typ",
            "styles/uralla.args",
            "scripts/transform_places.xml",
        ):
            _touch(root / path)
        for path in (
            "data/input/bounds.zip",
            "data/input/sea.zip",
            "data/input/source.osm.pbf",
            "data/input/geonames.zip",
            "data/elevation/test.osm.pbf",
            "data/poly/test.poly",
        ):
            _touch(root / path)
        (root / "data/dem").mkdir(parents=True)
        (root / "work").mkdir()
        (root / "publish/mapsource").mkdir(parents=True)
        _touch(root / "tools/mkgmap-r4924/mkgmap.jar")
        _touch(root / "tools/splitter-r654/splitter.jar")
        lock = root / "tools.lock.yaml"
        lock.write_text(
            """schema_version: 1
java:
  minimum_major: 17
mkgmap:
  install_dir: mkgmap-r4924
  jar: mkgmap.jar
  archive: mkgmap-r4924.zip
  sha256: null
splitter:
  install_dir: splitter-r654
  jar: splitter.jar
  archive: splitter-r654.zip
  sha256: null
""",
            encoding="utf-8",
        )
        return lock

    def test_ready_host_has_no_errors(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            lock = self._prepare(root)
            checks = run_doctor(
                _manifest(),
                self._host(root),
                root,
                lock,
                check_commands=False,
                check_external_data=True,
                probe_publish=True,
            )
            self.assertFalse(has_errors(checks), [check for check in checks if check.status == "error"])
            self.assertTrue(any(check.status == "warning" for check in checks))
            self.assertTrue(
                any(
                    check.name == "data:poly/test.poly" and check.status == "ok"
                    for check in checks
                )
            )

    def test_missing_external_file_is_an_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            lock = self._prepare(root)
            (root / "data/elevation/test.osm.pbf").unlink()
            checks = run_doctor(
                _manifest(),
                self._host(root),
                root,
                lock,
                check_commands=False,
                check_external_data=True,
                probe_publish=False,
            )
            self.assertTrue(has_errors(checks))
            self.assertTrue(
                any(check.name == "data:elevation/test.osm.pbf" and check.status == "error" for check in checks)
            )


if __name__ == "__main__":
    unittest.main()

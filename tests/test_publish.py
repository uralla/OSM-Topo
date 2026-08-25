from __future__ import annotations

from pathlib import Path
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from uralla_build.errors import StageError
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy
from uralla_build.publish import gmapi_zip_name, publication_targets, publish_product


def _host(root: Path) -> HostConfig:
    return HostConfig(
        HostPaths(root / "data", root / "work", root / "publish", root / "tools", root / "dem"),
        PublicationPolicy(".", "mapsource", False, "store", False),
        1,
        0,
    )


PRODUCT = {"names": {"output_img": "Topo-Ural-N.img"}}


class PublicationTests(unittest.TestCase):
    def test_legacy_output_name_is_preserved(self) -> None:
        self.assertEqual(gmapi_zip_name("Topo-Ural-N.img"), "Topo-Ural-N-ms.zip")

    def test_plan_uses_ready_and_mapsource_directories(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            targets = publication_targets(_host(root), PRODUCT, root / "map.img", root / "map.gmap")
            self.assertEqual(Path(targets[0].target), root / "publish/Topo-Ural-N.img")
            self.assertEqual(Path(targets[1].target), root / "publish/mapsource/Topo-Ural-N-ms.zip")

    def test_img_and_single_store_zip_are_published(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            img = root / "source.img"
            img.write_bytes(b"garmin-img")
            gmapi = root / "Topo-Ural-N.gmap"
            (gmapi / "Contents/Resources").mkdir(parents=True)
            (gmapi / "Contents/Info.xml").write_text("<info/>", encoding="utf-8")
            (gmapi / "Contents/Resources/tile.img").write_bytes(b"tile")

            artifacts = publish_product(_host(root), PRODUCT, img, gmapi)
            self.assertEqual(Path(artifacts[0].path).read_bytes(), b"garmin-img")
            self.assertEqual(Path(artifacts[0].path).stat().st_mode & 0o777, 0o644)
            archive_path = Path(artifacts[1].path)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
                self.assertTrue(
                    all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist())
                )
                self.assertIn("Topo-Ural-N.gmap/Contents/Info.xml", archive.namelist())

    def test_invalid_new_release_does_not_replace_previous_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            publish = root / "publish"
            (publish / "mapsource").mkdir(parents=True)
            previous_img = publish / "Topo-Ural-N.img"
            previous_zip = publish / "mapsource/Topo-Ural-N-ms.zip"
            previous_img.write_bytes(b"previous-img")
            previous_zip.write_bytes(b"previous-zip")
            empty_img = root / "empty.img"
            empty_img.touch()
            gmapi = root / "empty.gmap"
            gmapi.mkdir()

            with self.assertRaises(StageError):
                publish_product(_host(root), PRODUCT, empty_img, gmapi)
            self.assertEqual(previous_img.read_bytes(), b"previous-img")
            self.assertEqual(previous_zip.read_bytes(), b"previous-zip")

    def test_second_rename_failure_rolls_back_first_artifact(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            publish = root / "publish"
            (publish / "mapsource").mkdir(parents=True)
            previous_img = publish / "Topo-Ural-N.img"
            previous_zip = publish / "mapsource/Topo-Ural-N-ms.zip"
            previous_img.write_bytes(b"previous-img")
            previous_zip.write_bytes(b"previous-zip")
            img = root / "new.img"
            img.write_bytes(b"new-img")
            gmapi = root / "Topo-Ural-N.gmap"
            gmapi.mkdir()
            (gmapi / "Info.xml").write_text("new", encoding="utf-8")

            real_replace = os.replace
            failed = False

            def fail_second_replace(source: object, target: object) -> None:
                nonlocal failed
                if Path(target) == previous_zip and not failed:
                    failed = True
                    raise OSError("simulated second rename failure")
                real_replace(source, target)

            with patch("uralla_build.publish.os.replace", side_effect=fail_second_replace):
                with self.assertRaises(StageError):
                    publish_product(_host(root), PRODUCT, img, gmapi)
            self.assertEqual(previous_img.read_bytes(), b"previous-img")
            self.assertEqual(previous_zip.read_bytes(), b"previous-zip")


if __name__ == "__main__":
    unittest.main()

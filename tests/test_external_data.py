from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from uralla_build.external_data import has_refresh_errors, refresh_supplemental_data
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy


class ExternalDataRefreshTests(unittest.TestCase):
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

    @staticmethod
    def _manifest() -> dict[str, object]:
        return {"defaults": {"bounds": "input/bounds-latest.zip", "sea": "input/sea-latest.zip"}}

    @staticmethod
    def _zip(path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("payload.txt", payload)

    def test_successful_refresh_replaces_archives(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def downloader(url: str, target: Path) -> None:
                self._zip(target, url)

            results = refresh_supplemental_data(self._manifest(), self._host(root), downloader=downloader)
            self.assertFalse(has_refresh_errors(results))
            self.assertTrue(all(result.status == "updated" for result in results))
            for name in ("bounds-latest.zip", "sea-latest.zip"):
                with zipfile.ZipFile(root / "data/input" / name) as archive:
                    self.assertIn("https://www.thkukuk.de/", archive.read("payload.txt").decode("utf-8"))
            with zipfile.ZipFile(root / "data/input/cities15000.zip") as archive:
                self.assertIn("https://download.geonames.org/", archive.read("payload.txt").decode("utf-8"))

    def test_failed_refresh_keeps_existing_archives_as_warning(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("bounds-latest.zip", "sea-latest.zip", "cities15000.zip"):
                self._zip(root / "data/input" / name, "old")

            def downloader(url: str, target: Path) -> None:
                raise OSError("offline")

            results = refresh_supplemental_data(self._manifest(), self._host(root), downloader=downloader)
            self.assertFalse(has_refresh_errors(results))
            self.assertTrue(all(result.status == "warning" for result in results))
            for name in ("bounds-latest.zip", "sea-latest.zip", "cities15000.zip"):
                with zipfile.ZipFile(root / "data/input" / name) as archive:
                    self.assertEqual(archive.read("payload.txt"), b"old")

    def test_failed_refresh_without_fallback_is_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def downloader(url: str, target: Path) -> None:
                raise OSError("offline")

            results = refresh_supplemental_data(self._manifest(), self._host(root), downloader=downloader)
            self.assertTrue(has_refresh_errors(results))
            self.assertTrue(all(result.status == "error" for result in results))


if __name__ == "__main__":
    unittest.main()

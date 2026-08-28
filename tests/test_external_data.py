from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from uralla_build.external_data import _download, has_refresh_errors, refresh_supplemental_data
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

    def test_reporter_receives_progress_messages(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            messages: list[str] = []

            def downloader(url: str, target: Path) -> None:
                self._zip(target, url)

            results = refresh_supplemental_data(
                self._manifest(),
                self._host(root),
                downloader=downloader,
                reporter=messages.append,
            )
            self.assertFalse(has_refresh_errors(results))
            joined = "\n".join(messages)
            self.assertIn("[bounds] local: missing", joined)
            self.assertIn("[bounds] download:", joined)
            self.assertIn("validating ZIP", joined)
            self.assertIn("[geonames] updated:", joined)

    def test_builtin_downloader_reports_live_byte_progress(self) -> None:
        payload = b"x" * (10 * 1024 * 1024)
        events: list[tuple[int, int | None, float]] = []

        class FakeResponse:
            def __init__(self) -> None:
                self.headers = {"Content-Length": str(len(payload))}
                self.offset = 0

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self, size: int) -> bytes:
                chunk = payload[self.offset : self.offset + size]
                self.offset += len(chunk)
                return chunk

        with TemporaryDirectory() as directory:
            target = Path(directory) / "payload.zip"
            with patch("uralla_build.external_data.urlopen", return_value=FakeResponse()):
                _download(
                    "https://example.invalid/payload.zip",
                    target,
                    progress=lambda downloaded, total, elapsed: events.append(
                        (downloaded, total, elapsed)
                    ),
                )

            self.assertEqual(target.stat().st_size, len(payload))
            self.assertEqual(events[0][:2], (0, len(payload)))
            self.assertTrue(any(downloaded >= 8 * 1024 * 1024 for downloaded, _, _ in events))
            self.assertEqual(events[-1][0], len(payload))
            self.assertTrue(all(total == len(payload) for _, total, _ in events))

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

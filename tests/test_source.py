from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
import unittest
from unittest.mock import patch

from uralla_build.errors import StageError
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy
from uralla_build.source import _download, ensure_source, load_source_downloads


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _host(root: Path) -> HostConfig:
    return HostConfig(
        HostPaths(
            root / "data",
            root / "work",
            root / "publish",
            root / "tools",
            root / "dem",
        ),
        PublicationPolicy(".", "mapsource", False, "store", False),
        1,
        0,
    )


def _config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sources": {
            "russia": {
                "url": "https://example.invalid/russia-latest.osm.pbf",
                "refresh_days": 1,
            }
        },
    }


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._stream = BytesIO(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        self._stream.close()

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


class SourceDownloadTests(unittest.TestCase):
    def test_managed_download_config_includes_crimea(self) -> None:
        config = load_source_downloads(PROJECT_ROOT / "config/source-downloads.yaml")
        crimea = config["sources"]["crimea"]

        self.assertEqual(
            crimea["url"],
            "https://download.geofabrik.de/russia/crimean-fed-district-latest.osm.pbf",
        )
        self.assertEqual(crimea["refresh_days"], 1)

    def test_transient_503_is_retried_then_download_succeeds(self) -> None:
        with TemporaryDirectory() as directory:
            target = Path(directory) / "source.osm.pbf"
            error = HTTPError(
                "https://example.invalid/source.osm.pbf",
                503,
                "Service Unavailable",
                hdrs=None,
                fp=None,
            )
            with patch("uralla_build.source.urlopen", side_effect=[error, _Response(b"pbf-data")]) as opener:
                with patch("uralla_build.source.time.sleep") as sleeper:
                    _download("https://example.invalid/source.osm.pbf", target)

            self.assertEqual(target.read_bytes(), b"pbf-data")
            self.assertEqual(opener.call_count, 2)
            sleeper.assert_called_once_with(5)

    def test_permanent_404_is_not_retried(self) -> None:
        with TemporaryDirectory() as directory:
            target = Path(directory) / "source.osm.pbf"
            error = HTTPError(
                "https://example.invalid/source.osm.pbf",
                404,
                "Not Found",
                hdrs=None,
                fp=None,
            )
            with patch("uralla_build.source.urlopen", side_effect=error) as opener:
                with patch("uralla_build.source.time.sleep") as sleeper:
                    with self.assertRaises(HTTPError):
                        _download("https://example.invalid/source.osm.pbf", target)

            self.assertEqual(opener.call_count, 1)
            sleeper.assert_not_called()
            self.assertFalse(target.exists())

    def test_missing_source_is_downloaded_and_validated(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            calls: list[str] = []

            def downloader(url: str, target: Path) -> None:
                calls.append(f"download:{url}")
                self.assertTrue(target.name.endswith(".osm.pbf"))
                target.write_bytes(b"pbf-data")

            def validator(path: Path) -> None:
                calls.append(f"validate:{path.name}")

            result = ensure_source(
                "russia",
                {"path": "input/russia-latest.osm.pbf"},
                _host(root),
                _config(),
                downloader=downloader,
                validator=validator,
            )

            destination = root / "data/input/russia-latest.osm.pbf"
            self.assertEqual(result.action, "downloaded")
            self.assertEqual(destination.read_bytes(), b"pbf-data")
            self.assertEqual(len(calls), 2)
            self.assertFalse((destination.parent / ".russia-latest.partial.osm.pbf").exists())

    def test_fresh_source_is_reused_without_network(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "data/input/russia-latest.osm.pbf"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"existing")
            now = destination.stat().st_mtime + 3600

            def downloader(_url: str, _target: Path) -> None:
                self.fail("fresh source must not be downloaded")

            result = ensure_source(
                "russia",
                {"path": "input/russia-latest.osm.pbf"},
                _host(root),
                _config(),
                now=now,
                downloader=downloader,
                validator=lambda _path: None,
            )

            self.assertEqual(result.action, "reused")
            self.assertEqual(destination.read_bytes(), b"existing")

    def test_stale_source_is_atomically_replaced(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "data/input/russia-latest.osm.pbf"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"old")
            now = destination.stat().st_mtime + 2 * 86400

            def downloader(_url: str, target: Path) -> None:
                target.write_bytes(b"new")

            result = ensure_source(
                "russia",
                {"path": "input/russia-latest.osm.pbf"},
                _host(root),
                _config(),
                now=now,
                downloader=downloader,
                validator=lambda _path: None,
            )

            self.assertEqual(result.action, "updated")
            self.assertEqual(destination.read_bytes(), b"new")

    def test_failed_validation_preserves_previous_source(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "data/input/russia-latest.osm.pbf"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"good-old")
            now = destination.stat().st_mtime + 2 * 86400

            def downloader(_url: str, target: Path) -> None:
                target.write_bytes(b"broken-new")

            def validator(_path: Path) -> None:
                raise StageError("broken pbf")

            with self.assertRaisesRegex(StageError, "broken pbf"):
                ensure_source(
                    "russia",
                    {"path": "input/russia-latest.osm.pbf"},
                    _host(root),
                    _config(),
                    now=now,
                    downloader=downloader,
                    validator=validator,
                )

            self.assertEqual(destination.read_bytes(), b"good-old")
            self.assertFalse((destination.parent / ".russia-latest.partial.osm.pbf").exists())

    def test_unmanaged_source_is_left_alone(self) -> None:
        with TemporaryDirectory() as directory:
            result = ensure_source(
                "armenia",
                {"path": "input/armenia-latest.osm.pbf"},
                _host(Path(directory)),
                _config(),
            )
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

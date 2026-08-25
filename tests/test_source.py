from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy
from uralla_build.source import ensure_source


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


class SourceDownloadTests(unittest.TestCase):
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

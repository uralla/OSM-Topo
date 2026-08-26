from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
import zipfile

from uralla_build.bootstrap import (
    build_bootstrap_plan,
    install_pinned_tool,
)
from uralla_build.errors import ManifestError
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy


def _host(root: Path) -> HostConfig:
    return HostConfig(
        HostPaths(root / "data", root / "work", root / "publish", root / "tools", root / "dem"),
        PublicationPolicy(".", "mapsource", False, "store", False),
        1,
        0,
    )


def _tool_lock(checksum: str | None) -> dict[str, object]:
    return {
        "release": 1,
        "url": "https://example.invalid/tool-r1.zip",
        "archive": "tool-r1.zip",
        "sha256": checksum,
        "install_dir": "tool-r1",
        "jar": "tool.jar",
    }


def _plan_lock() -> dict[str, object]:
    return {
        "java": {"minimum_major": 17},
        "system_packages": {
            "ubuntu": {
                "java": "default-jre-headless",
                "osmium": "osmium-tool",
                "osmosis": "osmosis",
                "zip": "zip",
                "unzip": "unzip",
            },
            "macos": {
                "java": "openjdk",
                "osmium": "osmium-tool",
                "osmosis": "osmosis",
                "zip": "zip",
                "unzip": "unzip",
            },
        },
        "mkgmap": {"release": 4924, "install_dir": "mkgmap-r4924", "jar": "mkgmap.jar"},
        "splitter": {"release": 654, "install_dir": "splitter-r654", "jar": "splitter.jar"},
    }


def _create_archive(path: Path) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("tool-r1/tool.jar", b"jar-bytes")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BootstrapTests(unittest.TestCase):
    def test_plan_is_read_only_and_lists_missing_components(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = build_bootstrap_plan(_host(root), _plan_lock(), system="Linux", which=lambda _: None)
            self.assertTrue(any(action.kind == "system-install" for action in plan))
            self.assertEqual(sum(action.kind == "pinned-tool" for action in plan), 2)
            self.assertFalse((root / "tools").exists())

    def test_macos_java_launcher_without_runtime_installs_openjdk(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def which(command: str) -> str | None:
                return f"/usr/bin/{command}"

            plan = build_bootstrap_plan(
                _host(root),
                _plan_lock(),
                system="Darwin",
                which=which,
                java_major=lambda _: None,
            )
            installs = [action.command for action in plan if action.kind == "system-install"]
            self.assertEqual(installs, [("brew", "install", "openjdk")])

    def test_macos_supported_java_does_not_reinstall_openjdk(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def which(command: str) -> str | None:
                return f"/usr/bin/{command}"

            plan = build_bootstrap_plan(
                _host(root),
                _plan_lock(),
                system="Darwin",
                which=which,
                java_major=lambda _: 17,
            )
            self.assertFalse(any(action.kind == "system-install" for action in plan))

    def test_verified_archive_is_installed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.zip"
            checksum = _create_archive(source)
            lock_path = root / "tools.lock.yaml"
            lock_path.write_text("schema_version: 1\n", encoding="utf-8")

            def downloader(_: str, target: Path) -> None:
                shutil.copy2(source, target)

            installed = install_pinned_tool(
                "tool",
                _tool_lock(checksum),
                root / "tools",
                lock_path,
                capture_checksums=False,
                downloader=downloader,
            )
            self.assertEqual(installed.sha256, checksum)
            self.assertTrue((root / "tools/tool-r1/tool.jar").is_file())
            self.assertTrue((root / "tools/dist/tool-r1.zip").is_file())

    def test_unpinned_archive_requires_explicit_capture(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.zip"
            _create_archive(source)
            lock_path = root / "tools.lock.yaml"
            lock_path.write_text(
                """schema_version: 1
tool:
  sha256: null
""",
                encoding="utf-8",
            )

            def downloader(_: str, target: Path) -> None:
                shutil.copy2(source, target)

            with self.assertRaises(ManifestError):
                install_pinned_tool(
                    "tool",
                    _tool_lock(None),
                    root / "tools",
                    lock_path,
                    capture_checksums=False,
                    downloader=downloader,
                )
            self.assertFalse((root / "tools/tool-r1").exists())

    def test_checksum_capture_is_atomic_and_reviewable(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.zip"
            checksum = _create_archive(source)
            lock_path = root / "tools.lock.yaml"
            lock_path.write_text(
                """schema_version: 1
tool:
  release: 1
  sha256: null
""",
                encoding="utf-8",
            )

            def downloader(_: str, target: Path) -> None:
                shutil.copy2(source, target)

            install_pinned_tool(
                "tool",
                _tool_lock(None),
                root / "tools",
                lock_path,
                capture_checksums=True,
                downloader=downloader,
            )
            self.assertIn(f"sha256: {checksum}", lock_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

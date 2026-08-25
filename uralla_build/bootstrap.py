"""Safe, explicit bootstrap for system packages and pinned Java tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from typing import Any, Callable
from urllib.request import urlopen
import zipfile

import yaml

from .errors import ManifestError
from .host import HostConfig


COMMAND_KEYS = {
    "java": "java",
    "osmium": "osmium",
    "osmosis": "osmosis",
    "zip": "zip",
    "unzip": "unzip",
}


@dataclass(frozen=True, slots=True)
class BootstrapAction:
    kind: str
    description: str
    command: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["command"] = list(self.command) if self.command else None
        return result


@dataclass(frozen=True, slots=True)
class InstalledTool:
    name: str
    archive: Path
    install_dir: Path
    sha256: str


def load_tools_lock(path: str | Path) -> dict[str, Any]:
    lock_path = Path(path)
    try:
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ManifestError(f"cannot load tools lock {lock_path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ManifestError("tools lock must have schema_version: 1")
    return data


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def platform_key(system: str | None = None) -> str:
    current = system or platform.system()
    if current == "Linux":
        return "ubuntu"
    if current == "Darwin":
        return "macos"
    raise ManifestError(f"unsupported bootstrap platform: {current}")


def build_bootstrap_plan(
    host: HostConfig,
    lock: dict[str, Any],
    *,
    system: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[BootstrapAction]:
    """Return required actions without changing the machine."""

    key = platform_key(system)
    packages = lock.get("system_packages", {}).get(key)
    if not isinstance(packages, dict):
        raise ManifestError(f"system_packages.{key} must be a mapping")
    missing_keys = [name for name, command in COMMAND_KEYS.items() if which(command) is None]
    missing_packages = sorted({str(packages[name]) for name in missing_keys if name in packages})
    actions: list[BootstrapAction] = []
    if missing_packages:
        if key == "ubuntu":
            prefix: tuple[str, ...] = () if getattr(os, "geteuid", lambda: 1)() == 0 else ("sudo",)
            actions.append(BootstrapAction("system-update", "refresh apt package metadata", prefix + ("apt-get", "update")))
            actions.append(
                BootstrapAction(
                    "system-install",
                    "install missing Ubuntu packages",
                    prefix + ("apt-get", "install", "-y", *missing_packages),
                )
            )
        else:
            actions.append(
                BootstrapAction(
                    "system-install",
                    "install missing Homebrew formulae",
                    ("brew", "install", *missing_packages),
                )
            )

    for tool_name in ("mkgmap", "splitter"):
        tool = lock.get(tool_name)
        if not isinstance(tool, dict):
            raise ManifestError(f"{tool_name} lock entry must be a mapping")
        install_dir = host.paths.tools_root / str(tool.get("install_dir", ""))
        jar = install_dir / str(tool.get("jar", ""))
        if not jar.is_file():
            expected = tool.get("sha256")
            suffix = "" if expected else " (checksum capture required)"
            actions.append(
                BootstrapAction(
                    "pinned-tool",
                    f"download and install {tool_name} release {tool.get('release')}{suffix}",
                )
            )
    return actions


def _download(url: str, target: Path) -> None:
    with urlopen(url, timeout=120) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)


def _capture_checksum(lock_path: Path, tool_name: str, checksum: str) -> None:
    """Replace only the named top-level tool's null checksum, preserving YAML comments."""

    lines = lock_path.read_text(encoding="utf-8").splitlines(keepends=True)
    section: str | None = None
    replaced = False
    for index, line in enumerate(lines):
        if line and not line.startswith((" ", "\t", "#", "\n")) and line.rstrip().endswith(":"):
            section = line.rstrip()[:-1]
        if section == tool_name and line.strip() == "sha256: null":
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"  sha256: {checksum}{newline}"
            replaced = True
            break
    if not replaced:
        raise ManifestError(f"cannot capture checksum for {tool_name}: expected sha256: null")
    temporary = lock_path.with_suffix(lock_path.suffix + ".partial")
    temporary.write_text("".join(lines), encoding="utf-8")
    os.replace(temporary, lock_path)


def _safe_extract(zipped: zipfile.ZipFile, target: Path) -> None:
    root = target.resolve()
    for member in zipped.infolist():
        destination = (target / member.filename).resolve()
        if destination != root and root not in destination.parents:
            raise ManifestError(f"unsafe ZIP member: {member.filename}")
    zipped.extractall(target)


def install_pinned_tool(
    tool_name: str,
    tool: dict[str, Any],
    tools_root: Path,
    lock_path: Path,
    *,
    capture_checksums: bool,
    downloader: Callable[[str, Path], None] = _download,
) -> InstalledTool:
    """Download, verify and atomically admit one pinned distribution."""

    url = tool.get("url")
    archive_name = tool.get("archive")
    install_name = tool.get("install_dir")
    jar_name = tool.get("jar")
    if not all(isinstance(value, str) and value for value in (url, archive_name, install_name, jar_name)):
        raise ManifestError(f"incomplete lock entry for {tool_name}")

    tools_root.mkdir(parents=True, exist_ok=True)
    dist = tools_root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    archive = dist / archive_name
    install_dir = tools_root / install_name
    expected = tool.get("sha256")

    if install_dir.exists():
        jar = install_dir / jar_name
        if jar.is_file():
            if not archive.is_file():
                raise ManifestError(f"{tool_name} is installed but pinned archive is missing: {archive}")
            checksum = file_sha256(archive)
            if expected and checksum != expected:
                raise ManifestError(
                    f"{tool_name} installed archive SHA-256 mismatch: expected {expected}, found {checksum}"
                )
            if not expected:
                if not capture_checksums:
                    raise ManifestError(
                        f"{tool_name} installed archive has no pinned SHA-256; use --capture-checksums"
                    )
                _capture_checksum(lock_path, tool_name, checksum)
            return InstalledTool(tool_name, archive, install_dir, checksum)
        raise ManifestError(f"refusing to overwrite incomplete directory: {install_dir}")

    with tempfile.TemporaryDirectory(prefix=f".{tool_name}-", dir=tools_root) as temporary:
        temp_root = Path(temporary)
        downloaded = temp_root / archive_name
        downloader(url, downloaded)
        checksum = file_sha256(downloaded)
        if expected and checksum != expected:
            raise ManifestError(
                f"{tool_name} SHA-256 mismatch: expected {expected}, downloaded {checksum}"
            )
        if not expected and not capture_checksums:
            raise ManifestError(
                f"{tool_name} has no pinned SHA-256; rerun with --capture-checksums and review the lock diff"
            )

        extracted = temp_root / "extracted"
        extracted.mkdir()
        try:
            with zipfile.ZipFile(downloaded) as zipped:
                _safe_extract(zipped, extracted)
        except (OSError, zipfile.BadZipFile) as exc:
            raise ManifestError(f"cannot extract {tool_name}: {exc}") from exc

        candidate = extracted / install_name
        if not candidate.is_dir():
            children = [child for child in extracted.iterdir() if child.is_dir()]
            if len(children) == 1 and (children[0] / jar_name).is_file():
                candidate = children[0]
        if not (candidate / jar_name).is_file():
            raise ManifestError(f"{tool_name} archive does not contain {install_name}/{jar_name}")

        if not expected:
            _capture_checksum(lock_path, tool_name, checksum)

        staged_archive = dist / f".{archive_name}.partial"
        shutil.copy2(downloaded, staged_archive)
        os.replace(staged_archive, archive)
        candidate.rename(install_dir)
    return InstalledTool(tool_name, archive, install_dir, checksum)


def apply_bootstrap(
    host: HostConfig,
    lock_path: str | Path,
    *,
    capture_checksums: bool,
    install_system: bool = True,
    install_tools: bool = True,
) -> list[InstalledTool]:
    """Apply the explicit bootstrap plan; never called by doctor."""

    lock_file = Path(lock_path)
    lock = load_tools_lock(lock_file)
    plan = build_bootstrap_plan(host, lock)
    if install_system:
        for action in plan:
            if action.command is not None:
                subprocess.run(action.command, check=True)
    installed: list[InstalledTool] = []
    if install_tools:
        for tool_name in ("mkgmap", "splitter"):
            tool = lock.get(tool_name)
            if not isinstance(tool, dict):
                raise ManifestError(f"{tool_name} lock entry must be a mapping")
            jar = host.paths.tools_root / str(tool.get("install_dir", "")) / str(tool.get("jar", ""))
            if not jar.is_file():
                installed.append(
                    install_pinned_tool(
                        tool_name,
                        tool,
                        host.paths.tools_root,
                        lock_file,
                        capture_checksums=capture_checksums,
                    )
                )
    return installed

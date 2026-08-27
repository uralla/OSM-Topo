"""Read-only build-host diagnostics with a temporary atomic-rename probe."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

import yaml

from .errors import ManifestError
from .host import HostConfig, data_path, repo_path, validate_host_config
from .manifest import validate_manifest


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _check(name: str, ok: bool, detail: str, failure: str = "error") -> DoctorCheck:
    return DoctorCheck(name, "ok" if ok else failure, detail)


def _nearest_existing(path: Path) -> Path | None:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current if current.exists() else None


def _read_tools_lock(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ManifestError(f"cannot load tools lock {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ManifestError("tools lock must have schema_version: 1")
    return data


def _java_major() -> tuple[int | None, str]:
    java = shutil.which("java")
    if java is None:
        return None, "java not found"
    try:
        result = subprocess.run(
            [java, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        return None, str(exc)
    text = (result.stderr or result.stdout).strip().splitlines()
    summary = text[0] if text else "unknown java version"
    match = re.search(r'"(?:1\.)?([0-9]+)', summary)
    return (int(match.group(1)) if match else None), summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe_atomic_rename(directory: Path) -> tuple[bool, str]:
    if not directory.is_dir():
        return False, f"directory does not exist: {directory}"
    try:
        with tempfile.TemporaryDirectory(prefix=".uralla-doctor-", dir=directory) as temporary:
            root = Path(temporary)
            source = root / "probe.partial"
            target = root / "probe.ready"
            source.write_text("uralla-doctor\n", encoding="utf-8")
            os.replace(source, target)
            if target.read_text(encoding="utf-8") != "uralla-doctor\n":
                return False, "atomic rename content mismatch"
        return True, f"atomic rename works in {directory}"
    except OSError as exc:
        return False, str(exc)


def run_doctor(
    manifest: dict[str, Any],
    host: HostConfig,
    repo_root: str | Path,
    tools_lock_path: str | Path,
    *,
    check_commands: bool = True,
    check_external_data: bool = True,
    probe_publish: bool = True,
) -> list[DoctorCheck]:
    """Run deterministic checks and return all results without early exit."""

    root = Path(repo_root).resolve()
    checks: list[DoctorCheck] = []

    manifest_issues = validate_manifest(manifest)
    checks.append(
        _check(
            "manifest",
            not manifest_issues,
            f"{len(manifest.get('products', {}))}-product manifest is structurally valid"
            if not manifest_issues
            else "; ".join(map(str, manifest_issues)),
        )
    )
    host_issues = validate_host_config(host)
    checks.append(
        _check(
            "host-config",
            not host_issues,
            "host publication/resource policy is valid"
            if not host_issues
            else "; ".join(map(str, host_issues)),
        )
    )

    system = platform.system()
    checks.append(_check("platform", system in {"Linux", "Darwin"}, f"{system} {platform.machine()}"))
    package_manager = "apt-get" if system == "Linux" else "brew" if system == "Darwin" else None
    if check_commands:
        checks.append(
            _check(
                "package-manager",
                bool(package_manager and shutil.which(package_manager)),
                f"{package_manager or 'unsupported'}: {shutil.which(package_manager) if package_manager else 'missing'}",
            )
        )

    try:
        tools_lock = _read_tools_lock(Path(tools_lock_path))
    except ManifestError as exc:
        checks.append(_check("tools-lock", False, str(exc)))
        tools_lock = {}
    else:
        checks.append(_check("tools-lock", True, str(tools_lock_path)))

    if check_commands:
        minimum_java = int(tools_lock.get("java", {}).get("minimum_major", 17))
        major, detail = _java_major()
        checks.append(_check("java", major is not None and major >= minimum_java, detail))
        for command in ("osmium", "osmosis", "zip", "unzip"):
            resolved = shutil.which(command)
            checks.append(_check(f"command:{command}", resolved is not None, resolved or "not found"))
        has_python_osmium = importlib.util.find_spec("osmium") is not None
        checks.append(
            _check(
                "python:osmium",
                has_python_osmium,
                "Python osmium module installed"
                if has_python_osmium
                else "Python osmium module not found; install project dependencies",
            )
        )

    tools_root = host.paths.tools_root
    for tool_name in ("mkgmap", "splitter"):
        tool = tools_lock.get(tool_name)
        if not isinstance(tool, dict):
            continue
        jar = tools_root / str(tool.get("install_dir", "")) / str(tool.get("jar", ""))
        checks.append(_check(f"pinned:{tool_name}", jar.is_file(), str(jar)))
        archive = tools_root / "dist" / str(tool.get("archive", ""))
        expected = tool.get("sha256")
        if expected:
            actual = _sha256(archive) if archive.is_file() else None
            checks.append(_check(f"checksum:{tool_name}", actual == expected, actual or f"missing {archive}"))
        else:
            checks.append(
                DoctorCheck(
                    f"checksum:{tool_name}",
                    "warning",
                    "SHA-256 not captured yet; bootstrap must not silently trust this archive",
                )
            )

    defaults = manifest.get("defaults", {})
    project_paths: set[str] = set()
    for key in ("style", "typ", "mkgmap_args", "transform_places"):
        value = defaults.get(key)
        if isinstance(value, str):
            project_paths.add(value)
    preprocessor = defaults.get("preprocessor")
    if isinstance(preprocessor, dict) and isinstance(preprocessor.get("blacklist"), str):
        project_paths.add(preprocessor["blacklist"])
    for value in sorted(project_paths):
        path = repo_path(root, value)
        checks.append(_check(f"project:{value}", path.exists(), str(path)))

    if check_external_data:
        external_paths: set[str] = set()
        for key in ("bounds", "sea"):
            value = defaults.get(key)
            if isinstance(value, str):
                external_paths.add(value)
        for source in manifest.get("sources", {}).values():
            if isinstance(source, dict) and isinstance(source.get("path"), str):
                external_paths.add(source["path"])
        for product in manifest.get("products", {}).values():
            if not isinstance(product, dict):
                continue
            for key in ("polygon", "elevation", "geonames"):
                value = product.get(key)
                if isinstance(value, str):
                    external_paths.add(value)
        for value in sorted(external_paths):
            path = data_path(host, value)
            checks.append(_check(f"data:{value}", path.is_file(), str(path)))
        checks.append(_check("data:dem-root", host.paths.dem_root.is_dir(), str(host.paths.dem_root)))

    work_anchor = _nearest_existing(host.paths.work_root)
    if work_anchor is None:
        checks.append(_check("disk-space", False, f"no existing parent for {host.paths.work_root}"))
    else:
        free = shutil.disk_usage(work_anchor).free
        required = host.minimum_free_gib * 1024**3
        checks.append(
            _check(
                "disk-space",
                free >= required,
                f"{free / 1024**3:.1f} GiB free; minimum {host.minimum_free_gib} GiB",
            )
        )

    publish_img = host.paths.publish_root / host.publication.img_subdir
    publish_gmapi = host.paths.publish_root / host.publication.gmapi_subdir
    for label, directory in (("publish:img", publish_img), ("publish:gmapi", publish_gmapi)):
        checks.append(_check(label, directory.is_dir() and os.access(directory, os.W_OK), str(directory)))
    if probe_publish:
        ok, detail = _probe_atomic_rename(publish_img)
        checks.append(_check("publish:atomic-rename", ok, detail))
    return checks


def has_errors(checks: Iterable[DoctorCheck]) -> bool:
    return any(check.status == "error" for check in checks)

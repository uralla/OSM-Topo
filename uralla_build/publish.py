"""Validated same-filesystem staging and atomic publication."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping
from uuid import uuid4
import zipfile

from .basecamp_package import basecamp_installer_files
from .errors import StageError
from .host import HostConfig, validate_host_config


@dataclass(frozen=True, slots=True)
class PublicationTarget:
    kind: str
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class PublishedArtifact:
    kind: str
    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def gmapi_zip_name(output_img: str) -> str:
    name = Path(output_img).name
    if not name.lower().endswith(".img"):
        raise StageError(f"output_img must end in .img: {output_img!r}")
    # Keep the legacy public filename so existing download links remain valid.
    # The archive itself is now a BaseCamp-oriented GMAPI package.
    return f"{name[:-4]}-ms.zip"


def publication_targets(
    host: HostConfig,
    product: Mapping[str, object],
    img_source: str | Path,
    gmapi_source: str | Path,
) -> tuple[PublicationTarget, PublicationTarget]:
    issues = validate_host_config(host)
    if issues:
        raise StageError("; ".join(str(issue) for issue in issues))
    names = product.get("names")
    if not isinstance(names, Mapping) or not isinstance(names.get("output_img"), str):
        raise StageError("product.names.output_img is required")
    output_img = str(names["output_img"])
    img_target = host.paths.publish_root / host.publication.img_subdir / Path(output_img).name
    zip_target = (
        host.paths.publish_root
        / host.publication.gmapi_subdir
        / gmapi_zip_name(output_img)
    )
    return (
        PublicationTarget("img", str(Path(img_source)), str(img_target)),
        PublicationTarget("gmapi_zip", str(Path(gmapi_source)), str(zip_target)),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_img(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise StageError(f"IMG artifact is missing or empty: {path}")


def _gmapi_files(source: Path) -> list[Path]:
    if not source.is_dir():
        raise StageError(f"GMAPI source directory is missing: {source}")
    if not source.name.lower().endswith(".gmap"):
        raise StageError(f"GMAPI source directory must end in .gmap: {source}")
    files: list[Path] = []
    for entry in sorted(source.rglob("*")):
        if entry.is_symlink():
            raise StageError(f"GMAPI source contains a symlink: {entry}")
        if entry.is_file():
            files.append(entry)
    if not files:
        raise StageError(f"GMAPI source directory is empty: {source}")
    return files


def _write_store_zip(source: Path, target: Path) -> None:
    files = _gmapi_files(source)
    installer_files = basecamp_installer_files(source.name)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in files:
            archive.write(path, (Path(source.name) / path.relative_to(source)).as_posix())
        for name, payload in installer_files.items():
            archive.writestr(name, payload, compress_type=zipfile.ZIP_STORED)
    with zipfile.ZipFile(target, "r") as archive:
        if archive.testzip() is not None:
            raise StageError(f"GMAPI ZIP validation failed: {target}")
        names = set(archive.namelist())
        required = set(installer_files)
        if not required.issubset(names):
            missing = ", ".join(sorted(required - names))
            raise StageError(f"GMAPI ZIP is missing BaseCamp installer files: {missing}")
        if not archive.infolist() or any(
            item.compress_type != zipfile.ZIP_STORED for item in archive.infolist()
        ):
            raise StageError(f"GMAPI ZIP is not a single store archive: {target}")


def _stage_img(source: Path, target: Path) -> Path:
    _validate_img(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(descriptor)
    staged = Path(raw_path)
    try:
        shutil.copyfile(source, staged)
        os.chmod(staged, 0o644)
        _validate_img(staged)
        _fsync_file(staged)
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def _stage_gmapi(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.parent / f".{target.name}.{uuid4().hex}.tmp"
    try:
        _write_store_zip(source, staged)
        os.chmod(staged, 0o644)
        _fsync_file(staged)
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def _backup_existing(target: Path) -> Path:
    backup = target.parent / f".{target.name}.{uuid4().hex}.previous"
    try:
        os.link(target, backup)
    except OSError:
        shutil.copyfile(target, backup)
        _fsync_file(backup)
    return backup


def publish_product(
    host: HostConfig,
    product: Mapping[str, object],
    img_source: str | Path,
    gmapi_source: str | Path,
) -> tuple[PublishedArtifact, PublishedArtifact]:
    """Stage and validate both artifacts before replacing either release."""

    targets = publication_targets(host, product, img_source, gmapi_source)
    img_target = Path(targets[0].target)
    zip_target = Path(targets[1].target)
    staged: list[tuple[str, Path, Path]] = []
    backups: dict[Path, Path] = {}
    installed: list[Path] = []
    try:
        staged.append(("img", _stage_img(Path(img_source), img_target), img_target))
        staged.append(("gmapi_zip", _stage_gmapi(Path(gmapi_source), zip_target), zip_target))

        for _, _, target in staged:
            if target.exists():
                backup = _backup_existing(target)
                backups[target] = backup

        for _, temporary, target in staged:
            os.replace(temporary, target)
            installed.append(target)
            _fsync_directory(target.parent)
    except Exception as exc:
        for target in reversed(installed):
            backup = backups.get(target)
            try:
                if backup is not None and backup.exists():
                    os.replace(backup, target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, StageError):
            raise
        raise StageError(f"atomic publication failed: {exc}") from exc
    finally:
        for _, temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)

    artifacts = tuple(
        PublishedArtifact(kind, str(target), target.stat().st_size, _sha256(target))
        for kind, _, target in staged
    )
    return artifacts  # type: ignore[return-value]

"""Best-effort refresh of supplemental mkgmap datasets.

Downloads are staged and ZIP-validated before atomically replacing an existing
local archive. A failed refresh keeps the previous archive usable. Existing
archives are skipped when remote HTTP metadata confirms they are current.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
import os
from pathlib import Path
import tempfile
import time
from typing import Callable
from urllib.request import Request, urlopen
import zipfile

from .host import HostConfig, data_path


SUPPLEMENTAL_URLS = {
    "bounds": "https://www.thkukuk.de/osm/data/bounds-latest.zip",
    "sea": "https://www.thkukuk.de/osm/data/sea-latest.zip",
    "geonames": "https://download.geonames.org/export/dump/cities15000.zip",
}

OSM_SOURCE_URLS = {
    "russia": "https://download.geofabrik.de/russia-latest.osm.pbf",
    "northwestern": "https://download.geofabrik.de/russia/northwestern-fed-district-latest.osm.pbf",
    "crimea": "https://download.geofabrik.de/russia/crimean-fed-district-latest.osm.pbf",
    "belarus": "https://download.geofabrik.de/europe/belarus-latest.osm.pbf",
    "georgia": "https://download.geofabrik.de/europe/georgia-latest.osm.pbf",
    "turkey": "https://download.geofabrik.de/europe/turkey-latest.osm.pbf",
    "kazakhstan": "https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf",
    "kyrgyzstan": "https://download.geofabrik.de/asia/kyrgyzstan-latest.osm.pbf",
    "armenia": "https://download.geofabrik.de/asia/armenia-latest.osm.pbf",
    "mongolia": "https://download.geofabrik.de/asia/mongolia-latest.osm.pbf",
}

_DOWNLOAD_BLOCK = 1024 * 1024
_PROGRESS_STEP = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RefreshResult:
    name: str
    status: str
    target: str
    detail: str
    size: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RemoteMetadata:
    size: int | None
    modified_at: float | None


def _format_mib(value: int) -> str:
    return f"{value / (1024 * 1024):.1f} MiB"


def _remote_metadata(url: str) -> RemoteMetadata:
    request = Request(url, method="HEAD")
    with urlopen(request, timeout=60) as response:
        size_header = response.headers.get("Content-Length")
        try:
            size = int(size_header) if size_header is not None else None
        except ValueError:
            size = None

        modified_header = response.headers.get("Last-Modified")
        modified_at: float | None = None
        if modified_header:
            try:
                modified_at = parsedate_to_datetime(modified_header).timestamp()
            except (TypeError, ValueError, OverflowError):
                modified_at = None
        return RemoteMetadata(size=size, modified_at=modified_at)


def _is_current(target: Path, metadata: RemoteMetadata) -> bool:
    if not target.is_file() or metadata.size is None:
        return False
    stat = target.stat()
    if stat.st_size != metadata.size:
        return False
    if metadata.modified_at is None:
        return True
    return stat.st_mtime + 1.0 >= metadata.modified_at


def _download(
    url: str,
    target: Path,
    *,
    progress: Callable[[int, int | None, float], None] | None = None,
) -> None:
    with urlopen(url, timeout=180) as response, target.open("wb") as output:
        header = response.headers.get("Content-Length")
        try:
            total = int(header) if header is not None else None
        except ValueError:
            total = None

        started = time.monotonic()
        downloaded = 0
        next_report = _PROGRESS_STEP
        if progress is not None:
            progress(0, total, 0.0)

        while True:
            block = response.read(_DOWNLOAD_BLOCK)
            if not block:
                break
            output.write(block)
            downloaded += len(block)
            if progress is not None and downloaded >= next_report:
                progress(downloaded, total, max(time.monotonic() - started, 1e-9))
                next_report = downloaded + _PROGRESS_STEP

        if progress is not None and downloaded > 0:
            progress(downloaded, total, max(time.monotonic() - started, 1e-9))


def _validate_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        if not archive.namelist():
            raise zipfile.BadZipFile("empty ZIP archive")
        bad = archive.testzip()
        if bad is not None:
            raise zipfile.BadZipFile(f"CRC failure in {bad}")


def refresh_supplemental_data(
    manifest: dict[str, object],
    host: HostConfig,
    *,
    downloader: Callable[[str, Path], None] | None = None,
    reporter: Callable[[str], None] | None = None,
) -> list[RefreshResult]:
    defaults = manifest.get("defaults")
    if not isinstance(defaults, dict):
        return [RefreshResult("supplemental", "error", "", "manifest defaults are missing")]

    results: list[RefreshResult] = []
    resources = {
        "bounds": defaults.get("bounds"),
        "sea": defaults.get("sea"),
        "geonames": "input/cities15000.zip",
    }
    for name, value in resources.items():
        if not isinstance(value, str) or not value:
            results.append(RefreshResult(name, "error", "", f"supplemental {name} path is not configured"))
            continue
        target = data_path(host, value)
        target.parent.mkdir(parents=True, exist_ok=True)
        url = SUPPLEMENTAL_URLS[name]
        if reporter is not None:
            if target.is_file():
                reporter(f"[{name}] local: {target} ({target.stat().st_size} bytes)")
            else:
                reporter(f"[{name}] local: missing ({target})")

        remote_metadata: RemoteMetadata | None = None
        if downloader is None and target.is_file():
            try:
                if reporter is not None:
                    reporter(f"[{name}] checking remote metadata: {url}")
                remote_metadata = _remote_metadata(url)
                if _is_current(target, remote_metadata):
                    size = target.stat().st_size
                    if reporter is not None:
                        reporter(f"[{name}] up to date: {_format_mib(size)}; skipping download")
                    results.append(RefreshResult(name, "unchanged", str(target), "remote file is not newer", size))
                    continue
            except Exception as exc:
                if reporter is not None:
                    reporter(f"[{name}] metadata check unavailable: {exc}; downloading normally")

        if reporter is not None:
            reporter(f"[{name}] download: {url}")
        try:
            with tempfile.TemporaryDirectory(prefix=f".uralla-{name}-", dir=target.parent) as temp_dir:
                staged = Path(temp_dir) / target.name
                if downloader is None:
                    def report_download(downloaded: int, total: int | None, elapsed: float) -> None:
                        if reporter is None:
                            return
                        if downloaded == 0:
                            if total is None:
                                reporter(f"[{name}] receiving: size unknown")
                            else:
                                reporter(f"[{name}] receiving: 0.0 / {_format_mib(total)}")
                            return
                        speed = downloaded / max(elapsed, 1e-9)
                        if total:
                            percent = min(100.0, downloaded * 100 / total)
                            reporter(
                                f"[{name}] received: {_format_mib(downloaded)} / {_format_mib(total)} "
                                f"({percent:.1f}%) at {_format_mib(int(speed))}/s"
                            )
                        else:
                            reporter(
                                f"[{name}] received: {_format_mib(downloaded)} "
                                f"at {_format_mib(int(speed))}/s"
                            )

                    _download(url, staged, progress=report_download)
                else:
                    downloader(url, staged)
                if reporter is not None:
                    reporter(f"[{name}] downloaded: {staged.stat().st_size} bytes; validating ZIP")
                _validate_zip(staged)
                size = staged.stat().st_size
                if size <= 0:
                    raise OSError("downloaded archive is empty")
                replacement = target.parent / f".{target.name}.partial"
                if replacement.exists():
                    replacement.unlink()
                staged.replace(replacement)
                os.replace(replacement, target)
                if remote_metadata is not None and remote_metadata.modified_at is not None:
                    os.utime(target, (remote_metadata.modified_at, remote_metadata.modified_at))
            if reporter is not None:
                reporter(f"[{name}] updated: {target} ({size} bytes)")
            results.append(RefreshResult(name, "updated", str(target), url, size))
        except Exception as exc:
            if target.is_file():
                if reporter is not None:
                    reporter(f"[{name}] WARN: refresh failed; keeping existing archive: {exc}")
                results.append(
                    RefreshResult(
                        name,
                        "warning",
                        str(target),
                        f"refresh failed; keeping existing archive: {exc}",
                        target.stat().st_size,
                    )
                )
            else:
                if reporter is not None:
                    reporter(f"[{name}] ERROR: refresh failed and no local fallback exists: {exc}")
                results.append(
                    RefreshResult(
                        name,
                        "error",
                        str(target),
                        f"refresh failed and no local fallback exists: {exc}",
                    )
                )
    return results


def refresh_osm_source(
    manifest: dict[str, object],
    host: HostConfig,
    source_key: str,
    *,
    downloader: Callable[[str, Path], None] | None = None,
    reporter: Callable[[str], None] | None = None,
) -> RefreshResult:
    """Ensure one primary Geofabrik PBF exists and is current enough for a build.

    A new file is staged and atomically installed. If refresh fails but an older
    local PBF exists, keep it and continue with a warning; if no fallback exists,
    fail before the build pipeline starts.
    """
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        return RefreshResult(source_key, "error", "", "manifest sources are missing")
    source = sources.get(source_key)
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        return RefreshResult(source_key, "error", "", f"source {source_key!r} is not configured")
    url = OSM_SOURCE_URLS.get(source_key)
    if url is None:
        return RefreshResult(source_key, "error", "", f"no download URL configured for source {source_key!r}")

    target = data_path(host, source["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if reporter is not None:
        if target.is_file():
            reporter(f"[source:{source_key}] local: {target} ({_format_mib(target.stat().st_size)})")
        else:
            reporter(f"[source:{source_key}] local: missing ({target})")

    metadata: RemoteMetadata | None = None
    if downloader is None and target.is_file():
        try:
            if reporter is not None:
                reporter(f"[source:{source_key}] checking remote metadata: {url}")
            metadata = _remote_metadata(url)
            if _is_current(target, metadata):
                size = target.stat().st_size
                if reporter is not None:
                    reporter(f"[source:{source_key}] up to date: {_format_mib(size)}; skipping download")
                return RefreshResult(source_key, "unchanged", str(target), "remote file is not newer", size)
        except Exception as exc:
            if reporter is not None:
                reporter(f"[source:{source_key}] metadata check unavailable: {exc}; downloading normally")

    try:
        with tempfile.TemporaryDirectory(prefix=f".uralla-source-{source_key}-", dir=target.parent) as temp_dir:
            staged = Path(temp_dir) / target.name
            if reporter is not None:
                reporter(f"[source:{source_key}] download: {url}")
            if downloader is None:
                if reporter is not None:
                    reporter(f"[source:{source_key}] connecting...")
                def progress(downloaded: int, total: int | None, elapsed: float) -> None:
                    if reporter is None:
                        return
                    if downloaded == 0:
                        reporter(f"[source:{source_key}] receiving: " + (f"0.0 / {_format_mib(total)}" if total else "size unknown"))
                        return
                    speed = downloaded / max(elapsed, 1e-9)
                    if total:
                        reporter(f"[source:{source_key}] received: {_format_mib(downloaded)} / {_format_mib(total)} ({min(100.0, downloaded * 100 / total):.1f}%) at {_format_mib(int(speed))}/s")
                    else:
                        reporter(f"[source:{source_key}] received: {_format_mib(downloaded)} at {_format_mib(int(speed))}/s")
                _download(url, staged, progress=progress)
            else:
                downloader(url, staged)
            size = staged.stat().st_size
            if size <= 0:
                raise OSError("downloaded PBF is empty")
            replacement = target.parent / f".{target.name}.partial"
            if replacement.exists():
                replacement.unlink()
            staged.replace(replacement)
            os.replace(replacement, target)
            if metadata is not None and metadata.modified_at is not None:
                os.utime(target, (metadata.modified_at, metadata.modified_at))
        if reporter is not None:
            reporter(f"[source:{source_key}] updated: {target} ({_format_mib(size)})")
        return RefreshResult(source_key, "updated", str(target), url, size)
    except Exception as exc:
        if target.is_file() and target.stat().st_size > 0:
            if reporter is not None:
                reporter(f"[source:{source_key}] WARN: refresh failed; keeping existing PBF: {exc}")
            return RefreshResult(source_key, "warning", str(target), f"refresh failed; keeping existing PBF: {exc}", target.stat().st_size)
        if reporter is not None:
            reporter(f"[source:{source_key}] ERROR: refresh failed and no local fallback exists: {exc}")
        return RefreshResult(source_key, "error", str(target), f"refresh failed and no local fallback exists: {exc}")


def has_refresh_errors(results: list[RefreshResult]) -> bool:
    return any(result.status == "error" for result in results)

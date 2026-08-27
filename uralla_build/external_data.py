"""Best-effort refresh of supplemental mkgmap datasets.

Downloads are staged and ZIP-validated before atomically replacing an existing
local archive. A failed refresh keeps the previous archive usable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import tempfile
from typing import Callable
from urllib.request import urlopen
import zipfile

from .host import HostConfig, data_path


SUPPLEMENTAL_URLS = {
    "bounds": "https://www.thkukuk.de/osm/data/bounds-latest.zip",
    "sea": "https://www.thkukuk.de/osm/data/sea-latest.zip",
    "geonames": "https://download.geonames.org/export/dump/cities15000.zip",
}


@dataclass(frozen=True, slots=True)
class RefreshResult:
    name: str
    status: str
    target: str
    detail: str
    size: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _download(url: str, target: Path) -> None:
    with urlopen(url, timeout=180) as response, target.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)


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
    downloader: Callable[[str, Path], None] = _download,
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
            reporter(f"[{name}] download: {url}")
        try:
            with tempfile.TemporaryDirectory(prefix=f".uralla-{name}-", dir=target.parent) as temp_dir:
                staged = Path(temp_dir) / target.name
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
            if reporter is not None:
                reporter(f"[{name}] updated: {target} ({size} bytes)")
            results.append(RefreshResult(name, "updated", str(target), url, size))
        except Exception as exc:  # network, filesystem and invalid ZIP all use the same fallback policy
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


def has_refresh_errors(results: list[RefreshResult]) -> bool:
    return any(result.status == "error" for result in results)

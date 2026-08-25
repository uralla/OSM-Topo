"""Managed shared OSM source downloads for product builds."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Mapping
from urllib.request import urlopen

import yaml

from .errors import ManifestError, StageError
from .host import HostConfig, data_path


DEFAULT_SOURCE_DOWNLOADS = Path("config/source-downloads.yaml")


@dataclass(frozen=True, slots=True)
class SourceResult:
    source: str
    destination: str
    url: str
    action: str
    size: int
    age_days: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_source_downloads(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"cannot read source downloads {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"invalid source downloads YAML {config_path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ManifestError("source downloads must have schema_version: 1")
    sources = raw.get("sources")
    if not isinstance(sources, dict):
        raise ManifestError("source downloads sources must be a mapping")
    return raw


def _age_days(path: Path, now: float | None = None) -> float:
    current = time.time() if now is None else now
    return max(0.0, current - path.stat().st_mtime) / 86400.0


def _partial_path(destination: Path) -> Path:
    name = destination.name
    if name.endswith(".osm.pbf"):
        stem = name[: -len(".osm.pbf")]
        return destination.with_name(f".{stem}.partial.osm.pbf")
    return destination.with_name(f".{name}.partial")


def _download(url: str, target: Path) -> None:
    with urlopen(url, timeout=300) as response, target.open("wb") as output:
        raw_length = response.headers.get("Content-Length")
        expected = int(raw_length) if raw_length and raw_length.isdigit() else None
        copied = 0
        next_report = 256 * 1024 * 1024
        while True:
            block = response.read(8 * 1024 * 1024)
            if not block:
                break
            output.write(block)
            copied += len(block)
            if copied >= next_report:
                if expected:
                    percent = copied * 100.0 / expected
                    print(
                        f"[source] downloaded {copied / 1073741824:.2f} GiB / "
                        f"{expected / 1073741824:.2f} GiB ({percent:.1f}%)",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    print(
                        f"[source] downloaded {copied / 1073741824:.2f} GiB",
                        file=sys.stderr,
                        flush=True,
                    )
                next_report += 256 * 1024 * 1024
        output.flush()
        os.fsync(output.fileno())
    if expected is not None and copied != expected:
        raise StageError(
            f"source download size mismatch: expected {expected} bytes, received {copied}"
        )
    if copied == 0:
        raise StageError("source download is empty")


def _validate_pbf(path: Path) -> None:
    try:
        completed = subprocess.run(
            ("osmium", "fileinfo", str(path)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise StageError(f"cannot run osmium fileinfo: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise StageError(f"downloaded source PBF failed osmium validation: {detail}")


def ensure_source(
    source_key: str,
    source: Mapping[str, object],
    host: HostConfig,
    download_config: Mapping[str, object],
    *,
    now: float | None = None,
    downloader: Callable[[str, Path], None] = _download,
    validator: Callable[[Path], None] = _validate_pbf,
) -> SourceResult | None:
    downloads = download_config.get("sources")
    if not isinstance(downloads, Mapping):
        raise ManifestError("source downloads sources must be a mapping")
    rule = downloads.get(source_key)
    if rule is None:
        return None
    if not isinstance(rule, Mapping):
        raise ManifestError(f"source download rule {source_key!r} must be a mapping")

    url = rule.get("url")
    refresh_days = rule.get("refresh_days", 1)
    source_path = source.get("path")
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise ManifestError(f"source download rule {source_key!r} has invalid url")
    if not isinstance(refresh_days, int) or isinstance(refresh_days, bool) or refresh_days < 1:
        raise ManifestError(f"source download rule {source_key!r} refresh_days must be positive")
    if not isinstance(source_path, str) or not source_path:
        raise ManifestError(f"manifest source {source_key!r} has invalid path")

    destination = data_path(host, source_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    current_time = time.time() if now is None else now
    if destination.is_file() and destination.stat().st_size > 0:
        age = _age_days(destination, current_time)
        if age < refresh_days:
            return SourceResult(
                source_key,
                str(destination),
                url,
                "reused",
                destination.stat().st_size,
                age,
            )

    temporary = _partial_path(destination)
    temporary.unlink(missing_ok=True)
    previous_exists = destination.is_file()
    try:
        downloader(url, temporary)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise StageError(f"source downloader did not create a non-empty file: {temporary}")
        validator(temporary)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    age = _age_days(destination, current_time)
    return SourceResult(
        source_key,
        str(destination),
        url,
        "updated" if previous_exists else "downloaded",
        destination.stat().st_size,
        age,
    )


def ensure_product_source(
    manifest: Mapping[str, object],
    host: HostConfig,
    product_key: str,
    download_config: Mapping[str, object],
    **kwargs: object,
) -> SourceResult | None:
    products = manifest.get("products")
    sources = manifest.get("sources")
    if not isinstance(products, Mapping) or not isinstance(sources, Mapping):
        raise ManifestError("manifest products and sources must be mappings")
    product = products.get(product_key)
    if not isinstance(product, Mapping):
        raise StageError(f"unknown product: {product_key}")
    source_key = product.get("source")
    if not isinstance(source_key, str) or not source_key:
        raise ManifestError(f"product {product_key!r} has invalid source")
    source = sources.get(source_key)
    if not isinstance(source, Mapping):
        raise ManifestError(f"unknown source {source_key!r}")
    return ensure_source(source_key, source, host, download_config, **kwargs)

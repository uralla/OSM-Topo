"""Top-level CLI entry point with shared-source preparation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence

from .cli import main as cli_main
from .errors import ManifestError, StageError
from .host import load_host_config
from .manifest import load_manifest
from .source import DEFAULT_SOURCE_DOWNLOADS, ensure_product_source, load_source_downloads


def _option_value(argv: Sequence[str], name: str, default: str) -> str:
    try:
        index = argv.index(name)
    except ValueError:
        return default
    if index + 1 >= len(argv):
        return default
    return argv[index + 1]


def _build_product_request(argv: Sequence[str]) -> tuple[str, Path, Path, Path] | None:
    try:
        command_index = argv.index("build-product")
    except ValueError:
        return None
    if "--apply" not in argv or command_index + 1 >= len(argv):
        return None
    product = argv[command_index + 1]
    if product.startswith("-"):
        return None
    manifest = Path(_option_value(argv, "--manifest", "config/maps.yaml"))
    host = Path(_option_value(argv, "--host", "config/host.yaml"))
    repo_root = Path(_option_value(argv, "--repo-root", "."))
    return product, manifest, host, repo_root


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    request = _build_product_request(arguments)
    if request is not None:
        product, manifest_path, host_path, repo_root = request
        try:
            manifest = load_manifest(manifest_path)
            host = load_host_config(host_path, repo_root)
            downloads_path = (repo_root / DEFAULT_SOURCE_DOWNLOADS).resolve()
            downloads = load_source_downloads(downloads_path)
            result = ensure_product_source(manifest, host, product, downloads)
            if result is not None:
                print(
                    f"[source] {result.source}: {result.action}; "
                    f"{result.size / 1073741824:.2f} GiB -> {result.destination}",
                    file=sys.stderr,
                    flush=True,
                )
        except (ManifestError, StageError, OSError) as exc:
            print(f"ERROR source: {exc}", file=sys.stderr)
            return 1
    return cli_main(arguments)

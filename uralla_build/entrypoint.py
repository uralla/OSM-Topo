"""Top-level CLI entry point with shared-source preparation."""

from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

from .cli import main as cli_main
from .errors import ManifestError, StageError
from .history import HistoryStore
from .host import HostConfig, load_host_config
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


def _format_elapsed(seconds: float) -> str:
    total = max(int(round(seconds)), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{size} B"


def _build_version(host: HostConfig, build_id: str) -> str:
    history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
    build = history.get_build(build_id)
    if build is None:
        return "unknown"
    raw = str(build.get("created_at", ""))[:10]
    try:
        return date.fromisoformat(raw).strftime("%d.%m.%Y")
    except ValueError:
        return raw or "unknown"


def _human_build_summary(
    payload: Mapping[str, object],
    manifest: Mapping[str, object],
    host: HostConfig,
    product_key: str,
) -> str:
    result = payload.get("result")
    if not isinstance(result, Mapping):
        return json.dumps(payload, ensure_ascii=False, indent=2)

    products = manifest.get("products")
    product = products.get(product_key) if isinstance(products, Mapping) else None
    product = product if isinstance(product, Mapping) else {}
    names = product.get("names") if isinstance(product.get("names"), Mapping) else {}
    identity = product.get("identity") if isinstance(product.get("identity"), Mapping) else {}

    build_id = str(result.get("build_id", "unknown"))
    status = str(result.get("status", "unknown")).upper()
    family = str(names.get("family", product_key))
    version = _build_version(host, build_id)

    stages_raw = result.get("stages")
    stages = [stage for stage in stages_raw if isinstance(stage, Mapping)] if isinstance(stages_raw, list) else []
    total_seconds = sum(float(stage.get("duration_seconds", 0.0) or 0.0) for stage in stages)

    artifacts_raw = result.get("final_result")
    artifacts = [item for item in artifacts_raw if isinstance(item, Mapping)] if isinstance(artifacts_raw, list) else []

    width = 72
    rule = "═" * width
    thin = "─" * width
    lines = [
        rule,
        f"  BUILD COMPLETE — {family}" if status == "SUCCESS" else f"  BUILD {status} — {family}",
        rule,
        f"  Version        {version}",
        f"  Family ID      {identity.get('family_id', '-')}",
        f"  Product ID     {identity.get('product_id', '-')}",
        f"  Overview ID    {identity.get('overview_mapnumber', '-')}",
        f"  Tile range     {identity.get('first_tile_mapid', '-')} .. {identity.get('last_reserved_mapid', '-')}",
        f"  Build ID       {build_id}",
        f"  Status         {status}",
        "",
        "  Stages",
        f"  {'Stage':<24}{'Status':<12}{'Time':>10}",
        "  " + thin[:46],
    ]

    for stage in stages:
        name = str(stage.get("stage", "-"))
        stage_status = str(stage.get("status", "-")).upper()
        duration = _format_elapsed(float(stage.get("duration_seconds", 0.0) or 0.0))
        lines.append(f"  {name:<24}{stage_status:<12}{duration:>10}")
    lines.extend(
        [
            "  " + thin[:46],
            f"  {'TOTAL':<36}{_format_elapsed(total_seconds):>10}",
            "",
            "  Files",
            "  " + thin,
        ]
    )

    if artifacts:
        for artifact in artifacts:
            kind = str(artifact.get("kind", "file")).upper()
            path = str(artifact.get("path", "-"))
            size = _format_size(int(artifact.get("size", 0) or 0))
            lines.append(f"  {kind:<10}{size:>10}   {path}")
    else:
        lines.append("  no published files")

    lines.append(rule)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    request = _build_product_request(arguments)
    manifest: Mapping[str, object] | None = None
    host: HostConfig | None = None
    product: str | None = None
    if request is not None:
        product, manifest_path, host_path, repo_root = request
        try:
            manifest = load_manifest(manifest_path)
            host = load_host_config(host_path, repo_root)
            downloads_path = (repo_root / DEFAULT_SOURCE_DOWNLOADS).resolve()
            downloads = load_source_downloads(downloads_path)
            ensure_product_source(manifest, host, product, downloads)
        except (ManifestError, StageError, OSError) as exc:
            print(f"ERROR source: {exc}", file=sys.stderr)
            return 1

    human_summary = request is not None and "--json" not in arguments
    if not human_summary:
        return cli_main(arguments)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        status = cli_main(arguments)
    output = buffer.getvalue().strip()
    if not output:
        return status

    if status != 0 or manifest is None or host is None or product is None:
        print(output)
        return status

    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        print(output)
        return status
    if not isinstance(payload, Mapping):
        print(output)
        return status

    print(_human_build_summary(payload, manifest, host, product))
    return status

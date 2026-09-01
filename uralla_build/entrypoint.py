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
from .incremental import rebuild_from_mkgmap, rebuild_from_splitter
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


def _from_stage(argv: Sequence[str]) -> str | None:
    if "--from-stage" not in argv:
        return None
    value = _option_value(argv, "--from-stage", "")
    if not value:
        raise StageError("--from-stage requires a stage name")
    return value


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


def _last_json_mapping(output: str) -> Mapping[str, object] | None:
    """Return the last build payload from mixed human/machine stdout.

    Diagnostic text may legally appear both before and after the JSON payload.
    Prefer an object carrying ``result`` (the build-product payload), and only
    fall back to the last decodable mapping when no such object is present.
    """
    decoder = json.JSONDecoder()
    last_mapping: Mapping[str, object] | None = None
    last_payload: Mapping[str, object] | None = None
    for index, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, Mapping):
            continue
        last_mapping = value
        if "result" in value:
            last_payload = value
    return last_payload or last_mapping


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
    ]
    reused = payload.get("reused_build_id")
    if isinstance(reused, str) and reused:
        from_stage = payload.get("from_stage")
        reused_kind = "merge checkpoint" if from_stage == "splitter" else "splitter output"
        lines.append(f"  Reused build   {reused} ({reused_kind})")
    lines.extend(
        [
            "",
            "  Stages",
            f"  {'Stage':<24}{'Status':<12}{'Time':>10}",
            "  " + thin[:46],
        ]
    )

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
    try:
        from_stage = _from_stage(arguments)
    except StageError as exc:
        print(f"ERROR build-product: {exc}", file=sys.stderr)
        return 1

    if from_stage is not None and from_stage not in {"splitter", "mkgmap"}:
        print(
            f"ERROR build-product: --from-stage supports 'splitter' or 'mkgmap', got {from_stage!r}",
            file=sys.stderr,
        )
        return 1

    if request is not None:
        product, manifest_path, host_path, repo_root = request
        try:
            manifest = load_manifest(manifest_path)
            host = load_host_config(host_path, repo_root)
            if from_stage is None:
                downloads_path = (repo_root / DEFAULT_SOURCE_DOWNLOADS).resolve()
                downloads = load_source_downloads(downloads_path)
                ensure_product_source(manifest, host, product, downloads)
        except (ManifestError, StageError, OSError) as exc:
            print(f"ERROR source: {exc}", file=sys.stderr)
            return 1

    human_summary = request is not None and "--json" not in arguments

    if request is not None and from_stage == "splitter":
        assert manifest is not None and host is not None and product is not None
        tools_lock = Path(_option_value(arguments, "--tools-lock", "config/tools.lock.yaml"))
        build_id = _option_value(arguments, "--build-id", "") or None
        try:
            payload = rebuild_from_splitter(
                manifest,
                host,
                product_key=product,
                repo_root=repo_root,
                manifest_path=manifest_path,
                tools_lock_path=tools_lock,
                build_id=build_id,
            )
        except (ManifestError, StageError, OSError, ValueError) as exc:
            print(f"ERROR build-product: {exc}", file=sys.stderr)
            return 1
        result = payload.get("result")
        status = 0 if isinstance(result, Mapping) and result.get("status") == "success" else 1
        if "--json" in arguments:
            print(json.dumps({"ok": status == 0, "report": payload}, ensure_ascii=False, indent=2))
        else:
            print(_human_build_summary(payload, manifest, host, product))
        return status

    if request is not None and from_stage == "mkgmap":
        assert manifest is not None and host is not None and product is not None
        tools_lock = Path(_option_value(arguments, "--tools-lock", "config/tools.lock.yaml"))
        build_id = _option_value(arguments, "--build-id", "") or None
        try:
            payload = rebuild_from_mkgmap(
                manifest,
                host,
                product_key=product,
                repo_root=repo_root,
                manifest_path=manifest_path,
                tools_lock_path=tools_lock,
                build_id=build_id,
            )
        except (ManifestError, StageError, OSError, ValueError) as exc:
            print(f"ERROR build-product: {exc}", file=sys.stderr)
            return 1
        result = payload.get("result")
        status = 0 if isinstance(result, Mapping) and result.get("status") == "success" else 1
        if "--json" in arguments:
            print(json.dumps({"ok": status == 0, "report": payload}, ensure_ascii=False, indent=2))
        else:
            print(_human_build_summary(payload, manifest, host, product))
        return status

    if not human_summary:
        return cli_main(arguments)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        status = cli_main(arguments)
    output = buffer.getvalue().strip()
    if not output:
        return status

    if manifest is None or host is None or product is None:
        print(output)
        return status

    payload = _last_json_mapping(output)
    if payload is None:
        print(output)
        return status

    print(_human_build_summary(payload, manifest, host, product))
    return status

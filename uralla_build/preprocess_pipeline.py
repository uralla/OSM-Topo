"""Composite preprocess entry: semantic enrichment followed by deliberate area POIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from .area_pois import augment_area_pois
from .errors import StageError
from .preprocessor import _load_osmium, preprocess_pbf


def _report(message: str) -> None:
    if message.startswith("[preprocess] "):
        message = message[len("[preprocess] ") :]
    print(message, file=sys.stderr, flush=True)
    if sys.stderr.isatty():
        return
    try:
        with open("/dev/tty", "w", encoding="utf-8") as tty:
            print(message, file=tty, flush=True)
    except OSError:
        pass


def _run_osmium_rewrite(path: Path, command: list[str], suffix: str) -> None:
    """Rewrite one PBF atomically with an osmium command."""
    rewritten = path.parent / f".{path.name}.{uuid4().hex}.{suffix}.osm.pbf"
    try:
        completed = subprocess.run(
            [*command, "-O", str(path), "-o", str(rewritten)],
            check=False,
        )
        if completed.returncode != 0:
            raise StageError(
                f"{' '.join(command)} failed for area-POI output "
                f"with exit code {completed.returncode}"
            )
        rewritten.replace(path)
    finally:
        if rewritten.exists():
            rewritten.unlink()


def _sort_pbf(path: Path) -> None:
    """Restore canonical OSM object/id ordering after synthetic node insertion."""
    _run_osmium_rewrite(path, ["osmium", "sort"], "sorted")


def _renumber_nodes(path: Path) -> None:
    """Eliminate negative synthetic node IDs while preserving all node references.

    osmium versions agree on ordinary positive-ID ordering but older/newer stacks can
    disagree around negative IDs. This build artifact never leaves the Garmin build
    pipeline, so normalising node IDs is safer than carrying temporary negative IDs
    into the elevation merge. Ways and relations keep their original OSM IDs.
    """
    _run_osmium_rewrite(
        path,
        ["osmium", "renumber", "--object-type=node", "--start-id=1"],
        "renumbered",
    )


def run_preprocess_pipeline(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build preprocess")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--config", default=Path("config/preprocessor-blacklist.yaml"), type=Path
    )
    parser.add_argument("--profile", required=True, action="append")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)

    output = args.output.resolve()
    semantic = output.parent / f".{output.name}.{uuid4().hex}.semantic.osm.pbf"
    try:
        preprocess_pbf(
            args.input,
            semantic,
            args.config,
            args.profile,
            args.report,
        )
        osmium = _load_osmium()
        area_stats = augment_area_pois(
            semantic,
            output,
            osmium,
            reporter=_report,
        )
        _sort_pbf(output)
        _renumber_nodes(output)
        report_path = args.report.resolve()
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StageError(f"cannot update preprocess report with area POIs: {exc}") from exc
        if isinstance(report, dict):
            report["area_pois"] = area_stats
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR preprocess: {exc}", file=sys.stderr)
        return 1
    finally:
        if semantic.exists():
            semantic.unlink()

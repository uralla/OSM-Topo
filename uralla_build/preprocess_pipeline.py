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


def _sort_pbf(path: Path) -> None:
    """Restore canonical OSM object/id ordering after synthetic node insertion."""
    sorted_path = path.parent / f".{path.name}.{uuid4().hex}.sorted.osm.pbf"
    try:
        completed = subprocess.run(
            ["osmium", "sort", "-O", str(path), "-o", str(sorted_path)],
            check=False,
        )
        if completed.returncode != 0:
            raise StageError(
                f"osmium sort failed for area-POI output with exit code {completed.returncode}"
            )
        sorted_path.replace(path)
    finally:
        if sorted_path.exists():
            sorted_path.unlink()


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

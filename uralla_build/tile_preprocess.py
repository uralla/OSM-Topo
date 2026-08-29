"""Parallel semantic preprocessing for splitter tile sets."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import json
import os
import subprocess
from typing import Iterable

from .errors import StageError
from .preprocessor import preprocess_pbf


def _process_one(
    source: str,
    destination: str,
    report: str,
    config: str,
    profiles: tuple[str, ...],
    elevation: str | None,
) -> tuple[str, dict[str, object]]:
    src = Path(source)
    dst = Path(destination)
    rpt = Path(report)
    dst.parent.mkdir(parents=True, exist_ok=True)
    rpt.parent.mkdir(parents=True, exist_ok=True)

    if elevation is None:
        payload = preprocess_pbf(src, dst, Path(config), profiles, rpt)
        return src.name, payload

    temporary = dst.with_suffix(dst.suffix + ".preprocessed")
    try:
        payload = preprocess_pbf(src, temporary, Path(config), profiles, rpt)
        completed = subprocess.run(
            ["osmium", "merge", "-O", str(temporary), elevation, "-o", str(dst)],
            check=False,
            text=True,
        )
        if completed.returncode != 0:
            raise StageError(f"osmium merge failed for {src.name}: exit {completed.returncode}")
    finally:
        temporary.unlink(missing_ok=True)
    return src.name, payload


def _tile_files(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("*.osm.pbf") if path.is_file())


def _rewrite_template(template: Path, output: Path, tile_names: Iterable[str], tiles_dir: Path) -> None:
    names = set(tile_names)
    lines = template.read_text(encoding="utf-8").splitlines()
    replaced: set[str] = set()
    rendered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("input-file="):
            raw = stripped.split("=", 1)[1]
            name = Path(raw).name
            if name in names:
                prefix = line[: len(line) - len(line.lstrip())]
                rendered.append(f"{prefix}input-file={tiles_dir / name}")
                replaced.add(name)
                continue
        rendered.append(line)
    missing = names - replaced
    if missing:
        raise StageError(f"splitter template did not reference tiles: {', '.join(sorted(missing))}")
    output.write_text("\n".join(rendered) + "\n", encoding="utf-8")


def prepare_tiles(
    *,
    input_dir: Path,
    template: Path,
    output_dir: Path,
    config: Path,
    profiles: tuple[str, ...],
    report: Path,
    workers: int | None = None,
    elevation_dir: Path | None = None,
) -> dict[str, object]:
    """Preprocess splitter output in parallel and optionally merge matching DEM tiles."""

    sources = _tile_files(input_dir)
    if not sources:
        raise StageError(f"no splitter .osm.pbf tiles found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = output_dir / "reports"
    max_workers = workers or max(1, (os.cpu_count() or 2) - 1)
    max_workers = max(1, min(max_workers, len(sources)))

    jobs: list[tuple[str, str, str, str, tuple[str, ...], str | None]] = []
    for source in sources:
        elevation: str | None = None
        if elevation_dir is not None:
            match = elevation_dir / source.name
            if not match.is_file():
                raise StageError(f"missing matching elevation tile for {source.name}: {match}")
            elevation = str(match)
        jobs.append(
            (
                str(source),
                str(output_dir / source.name),
                str(reports_dir / f"{source.stem}.json"),
                str(config),
                profiles,
                elevation,
            )
        )

    results: dict[str, dict[str, object]] = {}
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_process_one, *job): Path(job[0]).name for job in jobs}
        for future in as_completed(futures):
            name = futures[future]
            try:
                tile_name, payload = future.result()
            except Exception as exc:
                raise StageError(f"tile preprocess failed for {name}: {exc}") from exc
            results[tile_name] = payload
            print(f"[preprocess-tiles] {len(results)}/{len(sources)} {tile_name}", flush=True)

    template_out = output_dir / "template.args"
    _rewrite_template(template, template_out, results, output_dir.resolve())
    summary: dict[str, object] = {
        "tiles": len(results),
        "workers": max_workers,
        "elevation_merged": elevation_dir is not None,
        "tile_reports": results,
    }
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m uralla_build.tile_preprocess")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--profile", required=True, action="append")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--elevation-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        prepare_tiles(
            input_dir=args.input_dir,
            template=args.template,
            output_dir=args.output_dir,
            config=args.config,
            profiles=tuple(args.profile),
            report=args.report,
            workers=args.workers,
            elevation_dir=args.elevation_dir,
        )
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR preprocess-tiles: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

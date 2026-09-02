"""Experimental preprocess pipeline using reusable parallel analysis artifacts."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid4

from .analysis_bundle import _analyze_worker, apply_analysis_bundle
from .area_pois import augment_area_pois
from .errors import StageError
from .preprocess_pipeline import _renumber_nodes, _report, _sort_pbf
from .preprocessor import _load_osmium
from .semantic_apply import apply_semantic_tags


def run_fast_preprocess(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build preprocess-fast")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", default=Path("config/preprocessor-blacklist.yaml"), type=Path)
    parser.add_argument("--profile", required=True, action="append")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--keep-analysis", action="store_true")
    args = parser.parse_args(argv)

    started = time.monotonic()
    output = args.output.resolve()
    source = args.input.resolve()
    root = output.parent
    run_token = uuid4().hex
    area = root / f".{output.name}.{run_token}.area-pois.osm.pbf"
    applied = root / f".{output.name}.{run_token}.analysis-applied.osm.pbf"
    owned_analysis_dir = args.analysis_dir is None
    analysis_dir = (
        root / f".{output.name}.{run_token}.analysis"
        if owned_analysis_dir
        else args.analysis_dir.resolve()
    )
    analysis_dir.mkdir(parents=True, exist_ok=True)
    road_artifact = analysis_dir / "road-density.json.gz"
    poi_artifact = analysis_dir / "poi-context.json.gz"

    try:
        osmium = _load_osmium()
        workers = max(1, int(args.workers))
        analysis_started = time.monotonic()
        analysis_stats: dict[str, object] = {}

        # Road density depends only on ways and their geometry, so it can start on
        # the untouched fresh PBF while area->POI synthesis runs in the main process.
        # POI context must wait for area synthesis because synthetic area POIs need
        # to participate in the same rarity/activity model as native OSM nodes.
        _report(
            "fast preprocess: road-density ANALYZE starts in parallel with area POI synthesis"
        )
        with ProcessPoolExecutor(max_workers=min(workers, 2)) as executor:
            road_future = executor.submit(
                _analyze_worker,
                "road_density",
                str(source),
                str(road_artifact),
            )

            _report("fast preprocess: area POI synthesis")
            area_started = time.monotonic()
            area_stats = augment_area_pois(source, area, osmium, reporter=_report)
            area_seconds = time.monotonic() - area_started

            _report("fast preprocess: POI-context ANALYZE starts on area-enriched PBF")
            poi_future = executor.submit(
                _analyze_worker,
                "poi_context",
                str(area),
                str(poi_artifact),
            )

            road_kind, road_seconds, road_stats = road_future.result()
            poi_kind, poi_seconds, poi_stats = poi_future.result()
            analysis_stats[road_kind] = {
                "seconds": round(road_seconds, 3),
                "artifact": str(road_artifact),
                "stats": road_stats,
            }
            analysis_stats[poi_kind] = {
                "seconds": round(poi_seconds, 3),
                "artifact": str(poi_artifact),
                "stats": poi_stats,
            }

        analyze_wall_seconds = time.monotonic() - analysis_started
        analysis_stats["wall_seconds"] = round(analyze_wall_seconds, 3)
        _report(
            "fast preprocess: staged ANALYZE complete; "
            f"road={road_seconds:.1f}s poi={poi_seconds:.1f}s wall={analyze_wall_seconds:.1f}s"
        )

        _report("fast preprocess: unified APPLY")
        apply_started = time.monotonic()
        apply_stats = apply_analysis_bundle(area, analysis_dir, applied, osmium, reporter=_report)
        apply_seconds = time.monotonic() - apply_started

        _report("fast preprocess: lightweight semantic pass")
        semantic_started = time.monotonic()
        semantic_report = apply_semantic_tags(
            applied,
            output,
            args.config,
            args.profile,
            args.report,
            osmium,
        )
        semantic_seconds = time.monotonic() - semantic_started

        sort_started = time.monotonic()
        _sort_pbf(output)
        _renumber_nodes(output)
        finalize_seconds = time.monotonic() - sort_started

        total_seconds = time.monotonic() - started
        report_path = args.report.resolve()
        report = {
            "schema_version": 2,
            "mode": "analyze-apply-staged",
            "input": str(source),
            "output": str(output),
            "timing": {
                "area_pois": round(area_seconds, 3),
                "analyze_wall": round(analyze_wall_seconds, 3),
                "road_analyze": round(road_seconds, 3),
                "poi_analyze": round(poi_seconds, 3),
                "apply": round(apply_seconds, 3),
                "semantic": round(semantic_seconds, 3),
                "sort_renumber": round(finalize_seconds, 3),
                "total": round(total_seconds, 3),
            },
            "area_pois": area_stats,
            "analysis": analysis_stats,
            "apply": apply_stats,
            "semantic": semantic_report,
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _report(
            "fast preprocess complete: "
            f"area={area_seconds:.1f}s analyze-wall={analyze_wall_seconds:.1f}s "
            f"apply={apply_seconds:.1f}s semantic={semantic_seconds:.1f}s "
            f"sort/renumber={finalize_seconds:.1f}s total={total_seconds:.1f}s"
        )
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR fast preprocess: {exc}", file=sys.stderr)
        return 1
    finally:
        for path in (area, applied):
            if path.exists():
                path.unlink()
        if owned_analysis_dir and not args.keep_analysis and analysis_dir.exists():
            shutil.rmtree(analysis_dir, ignore_errors=True)

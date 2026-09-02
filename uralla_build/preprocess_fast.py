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
from .area_poi_analysis import (
    analyze_area_pois,
    area_poi_reuse_entries_from_analysis,
    validate_area_poi_analysis,
)
from .area_pois import write_area_pois
from .errors import StageError
from .preprocess_pipeline import _renumber_nodes, _report, _sort_pbf
from .preprocessor import _load_osmium
from .semantic_apply import SemanticTransformer, apply_semantic_tags


ANALYSIS_MANIFEST = "analysis-manifest.json"
ANALYSIS_MANIFEST_SCHEMA = 4


def _source_identity(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _write_analysis_manifest(
    analysis_dir: Path,
    source: Path,
    area_stats: dict[str, int],
) -> None:
    payload = {
        "schema_version": ANALYSIS_MANIFEST_SCHEMA,
        "source": _source_identity(source),
        "reuse_scope": {
            "source_name": source.name,
            "policy": "same extract name; per-object freshness guards",
        },
        "semantic_basis": "area-poi + semantic/filter before spatial analysis",
        "artifacts": {
            "area_pois": "area-pois.json.gz",
            "road_density": "road-density.json.gz",
            "poi_context": "poi-context.json.gz",
        },
        "area_pois": {
            "created": int(area_stats.get("created", 0)),
            "candidates": int(area_stats.get("candidates", 0)),
        },
    }
    target = analysis_dir / ANALYSIS_MANIFEST
    temporary = analysis_dir / f".{ANALYSIS_MANIFEST}.{uuid4().hex}.partial"
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(target)


def _validate_reusable_analysis(
    analysis_dir: Path,
    source: Path,
) -> dict[str, object]:
    area_artifact = analysis_dir / "area-pois.json.gz"
    road_artifact = analysis_dir / "road-density.json.gz"
    poi_artifact = analysis_dir / "poi-context.json.gz"
    manifest_path = analysis_dir / ANALYSIS_MANIFEST
    for path in (area_artifact, road_artifact, poi_artifact, manifest_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise StageError(f"reusable analysis is incomplete: missing {path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageError(f"cannot read reusable analysis manifest {manifest_path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != ANALYSIS_MANIFEST_SCHEMA:
        raise StageError(
            "reusable analysis manifest has an unsupported schema; rebuild the analysis cache"
        )
    source_metadata = payload.get("source")
    if not isinstance(source_metadata, dict):
        raise StageError("reusable analysis manifest has incomplete source metadata")
    cached_name = str(source_metadata.get("name") or "")
    if cached_name and cached_name != source.name:
        raise StageError(
            f"reusable analysis was built for {cached_name}, not {source.name}"
        )
    validate_area_poi_analysis(area_artifact, source)
    return payload


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
    parser.add_argument(
        "--reuse-analysis",
        action="store_true",
        help=(
            "Reuse area/road/POI artifacts for newer extracts with the same source "
            "name; stale objects are skipped by cheap per-object guards"
        ),
    )
    args = parser.parse_args(argv)

    if args.reuse_analysis and args.analysis_dir is None:
        parser.error("--reuse-analysis requires a persistent --analysis-dir")

    started = time.monotonic()
    output = args.output.resolve()
    source = args.input.resolve()
    root = output.parent
    run_token = uuid4().hex
    area = root / f".{output.name}.{run_token}.area-pois.osm.pbf"
    semantic_base = root / f".{output.name}.{run_token}.semantic-base.osm.pbf"
    semantic_base_report_path = root / f".{output.name}.{run_token}.semantic-base.json"
    owned_analysis_dir = args.analysis_dir is None
    analysis_dir = (
        root / f".{output.name}.{run_token}.analysis"
        if owned_analysis_dir
        else args.analysis_dir.resolve()
    )
    analysis_dir.mkdir(parents=True, exist_ok=True)
    area_artifact = analysis_dir / "area-pois.json.gz"
    road_artifact = analysis_dir / "road-density.json.gz"
    poi_artifact = analysis_dir / "poi-context.json.gz"

    try:
        osmium = _load_osmium()
        workers = max(1, int(args.workers))
        analysis_stats: dict[str, object] = {}
        semantic_base_seconds = 0.0
        reusable_area_entries = ()

        if args.reuse_analysis:
            area_started = time.monotonic()
            manifest = _validate_reusable_analysis(analysis_dir, source)
            reusable_area_entries = tuple(area_poi_reuse_entries_from_analysis(area_artifact))
            area_seconds = time.monotonic() - area_started
            area_stats = {
                "candidates": len(reusable_area_entries),
                "created": len(reusable_area_entries),
                "reused": 1,
            }
            analyze_wall_seconds = 0.0
            road_seconds = 0.0
            poi_seconds = 0.0
            analysis_stats = {
                "reused": True,
                "cache_source": manifest.get("source"),
                "fresh_source": _source_identity(source),
                "area_pois": {"artifact": str(area_artifact)},
                "road_density": {"artifact": str(road_artifact)},
                "poi_context": {"artifact": str(poi_artifact)},
                "wall_seconds": 0.0,
            }
            semantic_transformer = SemanticTransformer(args.config, args.profile)
            apply_input = source
            _report(
                "fast preprocess: reusable post-semantic artifacts accepted for fresh extract; "
                "spatial analysis skipped, per-object freshness guards enabled"
            )
        else:
            analysis_started = time.monotonic()

            _report("fast preprocess: area POI ANALYZE + materialize")
            area_started = time.monotonic()
            area_candidates, area_stats = analyze_area_pois(source, area_artifact, osmium)
            write_area_pois(source, area, area_candidates, osmium, reporter=_report)
            area_seconds = time.monotonic() - area_started

            # Match the production order exactly: area synthesis, then blacklist and
            # cheap semantic enrichment, then POI-context and road-density analysis.
            _report("fast preprocess: materialize semantic/filter base before spatial ANALYZE")
            semantic_base_started = time.monotonic()
            semantic_report = apply_semantic_tags(
                area,
                semantic_base,
                args.config,
                args.profile,
                semantic_base_report_path,
                osmium,
            )
            semantic_base_seconds = time.monotonic() - semantic_base_started

            _report("fast preprocess: road-density + POI-context ANALYZE in parallel on semantic base")
            with ProcessPoolExecutor(max_workers=min(workers, 2)) as executor:
                road_future = executor.submit(
                    _analyze_worker,
                    "road_density",
                    str(semantic_base),
                    str(road_artifact),
                )
                poi_future = executor.submit(
                    _analyze_worker,
                    "poi_context",
                    str(semantic_base),
                    str(poi_artifact),
                )
                road_kind, road_seconds, road_stats = road_future.result()
                poi_kind, poi_seconds, poi_stats = poi_future.result()

            analysis_stats["area_pois"] = {
                "seconds": round(area_seconds, 3),
                "artifact": str(area_artifact),
                "stats": area_stats,
            }
            analysis_stats["semantic_base"] = {
                "seconds": round(semantic_base_seconds, 3),
                "stats": semantic_report,
            }
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
            _write_analysis_manifest(analysis_dir, source, area_stats)
            _report(
                "fast preprocess: parity ANALYZE complete; "
                f"area={area_seconds:.1f}s semantic-base={semantic_base_seconds:.1f}s "
                f"road={road_seconds:.1f}s poi={poi_seconds:.1f}s wall={analyze_wall_seconds:.1f}s"
            )

            # The semantic base already contains synthetic nodes and all cheap
            # semantic/filter transformations, so the initial cache-building run can
            # apply hints directly without repeating semantics or reinjecting areas.
            semantic_transformer = None
            apply_input = semantic_base

        _report("fast preprocess: unified APPLY (semantic first on reuse)")
        apply_started = time.monotonic()
        apply_stats = apply_analysis_bundle(
            apply_input,
            analysis_dir,
            output,
            osmium,
            reporter=_report,
            semantic_transformer=semantic_transformer,
            reusable_area_entries=reusable_area_entries,
        )
        apply_seconds = time.monotonic() - apply_started

        if args.reuse_analysis:
            assert semantic_transformer is not None
            semantic_report = semantic_transformer.report(input_path=source, output_path=output)
            semantic_seconds = float(semantic_report.get("seconds", apply_seconds))
        else:
            semantic_seconds = semantic_base_seconds

        sort_started = time.monotonic()
        _sort_pbf(output)
        _renumber_nodes(output)
        finalize_seconds = time.monotonic() - sort_started

        total_seconds = time.monotonic() - started
        report_path = args.report.resolve()
        report = {
            "schema_version": 7,
            "mode": "reuse-fresh-extract" if args.reuse_analysis else "parity-analyze-apply",
            "input": str(source),
            "output": str(output),
            "timing": {
                "area_pois": round(area_seconds, 3),
                "semantic_base": round(semantic_base_seconds, 3),
                "analyze_wall": round(analyze_wall_seconds, 3),
                "road_analyze": round(road_seconds, 3),
                "poi_analyze": round(poi_seconds, 3),
                "apply_semantic": round(apply_seconds, 3),
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
            f"area={area_seconds:.1f}s semantic-base={semantic_base_seconds:.1f}s "
            f"analyze-wall={analyze_wall_seconds:.1f}s "
            f"apply+semantic={apply_seconds:.1f}s "
            f"sort/renumber={finalize_seconds:.1f}s total={total_seconds:.1f}s"
        )
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR fast preprocess: {exc}", file=sys.stderr)
        return 1
    finally:
        for path in (area, semantic_base, semantic_base_report_path):
            if path.exists():
                path.unlink()
        if owned_analysis_dir and not args.keep_analysis and analysis_dir.exists():
            shutil.rmtree(analysis_dir, ignore_errors=True)

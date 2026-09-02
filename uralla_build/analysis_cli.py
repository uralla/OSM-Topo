"""CLI entry points for reusable preprocessor analysis artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analysis_bundle import analyze_bundle, apply_analysis_bundle
from .errors import StageError
from .poi_context_analysis import analyze_poi_context, apply_poi_context_analysis
from .preprocessor import _load_osmium
from .road_density_analysis import analyze_road_density, apply_road_density_analysis


def _report(message: str) -> None:
    print(f"[analysis] {message}", flush=True)


def run_analyze_road_density(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build analyze-road-density")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        analyze_road_density(args.input, args.output, _load_osmium(), reporter=_report)
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR road-density analysis: {exc}")
        return 1


def run_apply_road_density(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build apply-road-density")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        apply_road_density_analysis(args.input, args.analysis, args.output, _load_osmium(), reporter=_report)
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR road-density apply: {exc}")
        return 1


def run_analyze_poi_context(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build analyze-poi-context")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        analyze_poi_context(args.input, args.output, _load_osmium(), reporter=_report)
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR POI-context analysis: {exc}")
        return 1


def run_apply_poi_context(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build apply-poi-context")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        apply_poi_context_analysis(args.input, args.analysis, args.output, _load_osmium(), reporter=_report)
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR POI-context apply: {exc}")
        return 1


def run_analyze_bundle(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build analyze-bundle")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        analyze_bundle(args.input, args.output_dir, workers=args.workers, reporter=_report)
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR analysis bundle: {exc}")
        return 1


def run_apply_bundle(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="uralla_build apply-analysis")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--analysis-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        apply_analysis_bundle(args.input, args.analysis_dir, args.output, _load_osmium(), reporter=_report)
        return 0
    except (StageError, OSError, ValueError) as exc:
        print(f"ERROR analysis apply: {exc}")
        return 1

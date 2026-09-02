from __future__ import annotations

from pathlib import Path
import sys

from .analysis_cli import (
    run_analyze_bundle,
    run_analyze_poi_context,
    run_analyze_road_density,
    run_apply_bundle,
    run_apply_poi_context,
    run_apply_road_density,
)
from .entrypoint import main
from .interactive import run_interactive
from .preprocess_fast import run_fast_preprocess
from .preprocess_pipeline import run_preprocess_pipeline


def _interactive_request(argv: list[str]) -> tuple[Path, Path] | None:
    host = Path("config/host.yaml")
    manifest = Path("config/maps.yaml")
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--host" and index + 1 < len(argv):
            host = Path(argv[index + 1])
            index += 2
            continue
        if token == "--manifest" and index + 1 < len(argv):
            manifest = Path(argv[index + 1])
            index += 2
            continue
        return None
    return manifest, host


arguments = sys.argv[1:]
interactive = _interactive_request(arguments)
if interactive is not None:
    manifest_path, host_path = interactive
    raise SystemExit(run_interactive(manifest_path=manifest_path, host_path=host_path))

if "preprocess-fast" in arguments:
    command_index = arguments.index("preprocess-fast")
    raise SystemExit(run_fast_preprocess(arguments[command_index + 1 :]))
if "analyze-bundle" in arguments:
    command_index = arguments.index("analyze-bundle")
    raise SystemExit(run_analyze_bundle(arguments[command_index + 1 :]))
if "apply-analysis" in arguments:
    command_index = arguments.index("apply-analysis")
    raise SystemExit(run_apply_bundle(arguments[command_index + 1 :]))
if "analyze-road-density" in arguments:
    command_index = arguments.index("analyze-road-density")
    raise SystemExit(run_analyze_road_density(arguments[command_index + 1 :]))
if "apply-road-density" in arguments:
    command_index = arguments.index("apply-road-density")
    raise SystemExit(run_apply_road_density(arguments[command_index + 1 :]))
if "analyze-poi-context" in arguments:
    command_index = arguments.index("analyze-poi-context")
    raise SystemExit(run_analyze_poi_context(arguments[command_index + 1 :]))
if "apply-poi-context" in arguments:
    command_index = arguments.index("apply-poi-context")
    raise SystemExit(run_apply_poi_context(arguments[command_index + 1 :]))
if "preprocess" in arguments:
    preprocess_index = arguments.index("preprocess")
    raise SystemExit(run_preprocess_pipeline(arguments[preprocess_index + 1 :]))

raise SystemExit(main(arguments))

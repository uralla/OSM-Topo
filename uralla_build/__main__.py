from __future__ import annotations

from pathlib import Path
import sys

from .analysis_cli import run_analyze_road_density, run_apply_road_density
from .entrypoint import main
from .interactive import run_interactive
from .preprocess_pipeline import run_preprocess_pipeline


def _interactive_request(argv: list[str]) -> tuple[Path, Path] | None:
    """Return global config paths when argv contains no actual subcommand.

    The generated workspace launcher always injects ``--host <path>`` even when
    the user runs ``start`` without arguments, so checking only ``len(argv)``
    would miss the normal interactive entry path.
    """

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
        # Any remaining token is a real CLI request (or an invalid one), which
        # must continue through argparse rather than being swallowed by the UI.
        return None
    return manifest, host


arguments = sys.argv[1:]
interactive = _interactive_request(arguments)
if interactive is not None:
    manifest_path, host_path = interactive
    raise SystemExit(
        run_interactive(manifest_path=manifest_path, host_path=host_path)
    )

# Experimental analyze/apply path.  These commands deliberately stay outside
# the normal build pipeline until a large-map benchmark proves the speedup.
if "analyze-road-density" in arguments:
    command_index = arguments.index("analyze-road-density")
    raise SystemExit(run_analyze_road_density(arguments[command_index + 1 :]))
if "apply-road-density" in arguments:
    command_index = arguments.index("apply-road-density")
    raise SystemExit(run_apply_road_density(arguments[command_index + 1 :]))

# Preprocessing is a composite operation: semantic/tag enrichment first, then
# deliberate selected area-to-POI synthesis. mkgmap's global area POI generator
# stays disabled so duplicate suppression and interior placement remain ours.
if "preprocess" in arguments:
    preprocess_index = arguments.index("preprocess")
    raise SystemExit(run_preprocess_pipeline(arguments[preprocess_index + 1 :]))

# All build-product paths deliberately pass through the shared entrypoint so
# full builds and incremental resumes use the same source policy and final UI.
raise SystemExit(main(arguments))

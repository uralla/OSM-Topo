from __future__ import annotations

from pathlib import Path
import sys

from .cli import main as cli_main
from .entrypoint import main
from .interactive import run_interactive


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

# The legacy top-level entrypoint still owns full builds and mkgmap-only rebuilds.
# Splitter-resume is implemented in the newer CLI layer, so route that request
# directly there instead of letting the legacy guard reject it first.
if "--from-stage" in arguments:
    index = arguments.index("--from-stage")
    if index + 1 < len(arguments) and arguments[index + 1] == "splitter":
        raise SystemExit(cli_main(arguments))

raise SystemExit(main(arguments))

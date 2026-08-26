"""Machine-local workspace helpers.

The Git checkout is source-only. setup.sh creates a launcher in the selected
workspace which knows the checkout, host config and virtualenv interpreter.
"""

from __future__ import annotations

import os
from pathlib import Path
import shlex


def _absolute_without_resolving(path: Path) -> Path:
    """Return an absolute path without dereferencing its final symlink.

    Virtualenv ``bin/python`` is normally a symlink to the base interpreter.
    Resolving that symlink would make the generated launcher bypass the venv and
    lose installed project dependencies.
    """

    return Path(os.path.abspath(os.fspath(path)))


def launcher_text(repo_root: Path, host_config: Path, python: Path) -> str:
    """Return a self-contained shell launcher for one configured build machine."""

    repo = shlex.quote(str(repo_root.resolve()))
    host = shlex.quote(str(host_config.resolve()))
    interpreter = shlex.quote(str(_absolute_without_resolving(python)))
    return f"""#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT={repo}
HOST_CONFIG={host}
PYTHON={interpreter}

if [[ ! -d \"$REPO_ROOT\" ]]; then
  printf '[start] ERROR: repository not found: %s\\n' \"$REPO_ROOT\" >&2
  printf '[start] Run setup.sh again from the current repository checkout.\\n' >&2
  exit 1
fi
if [[ ! -f \"$HOST_CONFIG\" ]]; then
  printf '[start] ERROR: host config not found: %s\\n' \"$HOST_CONFIG\" >&2
  printf '[start] Run setup.sh again to recreate the workspace configuration.\\n' >&2
  exit 1
fi
if [[ ! -x \"$PYTHON\" ]]; then
  printf '[start] ERROR: configured Python is not available: %s\\n' \"$PYTHON\" >&2
  printf '[start] Run setup.sh again to recreate the virtual environment.\\n' >&2
  exit 1
fi

# Commands are launched from the repository internally so all project-relative
# defaults (manifest, tools lock, styles, polygons) continue to work. The user
# can stay in the machine-local workspace for normal operation.
cd \"$REPO_ROOT\"
exec \"$PYTHON\" -m uralla_build --host \"$HOST_CONFIG\" \"$@\"
"""


def write_launcher(path: Path, repo_root: Path, host_config: Path, python: Path) -> None:
    """Atomically create/update an executable workspace launcher."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(launcher_text(repo_root, host_config, python), encoding="utf-8")
    temporary.chmod(0o755)
    os.replace(temporary, path)

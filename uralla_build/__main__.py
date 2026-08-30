from __future__ import annotations

import sys

from .entrypoint import main
from .interactive import run_interactive


if len(sys.argv) == 1:
    raise SystemExit(run_interactive())

raise SystemExit(main())

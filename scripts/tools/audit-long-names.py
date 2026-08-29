#!/usr/bin/env python3
"""Audit overlong OSM names and recurring shortening candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

from uralla_build.long_names_audit import DEFAULT_EXAMPLES, DEFAULT_LIMIT, DEFAULT_TOP, audit_pbf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan an OSM PBF for name values longer than a limit and report common words/phrases."
    )
    parser.add_argument("input", type=Path, help="input .osm.pbf file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/long-names-report"),
        help="output prefix (default: output/long-names-report)",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="maximum acceptable name length")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help="number of top terms per section")
    parser.add_argument(
        "--examples",
        type=int,
        default=DEFAULT_EXAMPLES,
        help="examples retained per tag/term",
    )
    args = parser.parse_args()
    audit_pbf(
        args.input,
        args.output,
        limit=args.limit,
        top=args.top,
        example_limit=args.examples,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

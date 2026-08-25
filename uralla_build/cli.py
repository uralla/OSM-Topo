"""Command line entry point for build-system validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .errors import ManifestError, ValidationIssue
from .manifest import load_manifest, validate_manifest
from .ranges import validate_generated_range


def _emit(issues: list[ValidationIssue], report: object | None, as_json: bool) -> int:
    if as_json:
        print(
            json.dumps(
                {
                    "ok": not issues,
                    "issues": [
                        {"location": issue.location, "message": issue.message}
                        for issue in issues
                    ],
                    "report": report,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if issues:
            for issue in issues:
                print(f"ERROR {issue}", file=sys.stderr)
        else:
            print("OK")
        if report is not None:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if issues else 0


def _validate_manifest(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.manifest)
    except ManifestError as exc:
        return _emit([ValidationIssue("manifest", str(exc))], None, args.json)
    issues = validate_manifest(data)
    products = data.get("products") if isinstance(data.get("products"), dict) else {}
    report = {"products": len(products)}
    return _emit(issues, report, args.json)


def _validate_areas(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.manifest)
    except ManifestError as exc:
        return _emit([ValidationIssue("manifest", str(exc))], None, args.json)
    manifest_issues = validate_manifest(data)
    products = data.get("products") if isinstance(data.get("products"), dict) else {}
    product = products.get(args.product)
    if not isinstance(product, dict):
        manifest_issues.append(ValidationIssue("product", f"unknown product {args.product!r}"))
        return _emit(manifest_issues, None, args.json)
    issues, report = validate_generated_range(
        args.product,
        product["identity"],
        args.areas,
        args.template,
    )
    return _emit(manifest_issues + issues, report, args.json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uralla-build")
    parser.add_argument("--manifest", default=Path("config/maps.yaml"), type=Path)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("validate-manifest")
    manifest_parser.set_defaults(handler=_validate_manifest)

    areas_parser = subparsers.add_parser("validate-areas")
    areas_parser.add_argument("product")
    areas_parser.add_argument("areas", type=Path)
    areas_parser.add_argument("--template", type=Path)
    areas_parser.set_defaults(handler=_validate_areas)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())


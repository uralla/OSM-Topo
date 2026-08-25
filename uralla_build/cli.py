"""Command line entry point for build-system validation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .bootstrap import apply_bootstrap, build_bootstrap_plan, load_tools_lock
from .errors import ManifestError, StageError, ValidationIssue
from .doctor import has_errors, run_doctor
from .history import HistoryStore
from .host import load_host_config
from .manifest import load_manifest, validate_manifest
from .ranges import validate_generated_range
from .runner import StageRunner


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


def _doctor(args: argparse.Namespace) -> int:
    try:
        data = load_manifest(args.manifest)
        host = load_host_config(args.host, args.repo_root)
    except ManifestError as exc:
        return _emit([ValidationIssue("doctor", str(exc))], None, args.json)
    checks = run_doctor(
        data,
        host,
        args.repo_root,
        args.tools_lock,
        check_commands=not args.skip_tools,
        check_external_data=not args.skip_data,
        probe_publish=not args.skip_publish_probe,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not has_errors(checks),
                    "checks": [check.to_dict() for check in checks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for check in checks:
            print(f"{check.status.upper():7} {check.name}: {check.detail}")
    return 1 if has_errors(checks) else 0


def _bootstrap(args: argparse.Namespace) -> int:
    try:
        host = load_host_config(args.host, args.repo_root)
        lock = load_tools_lock(args.tools_lock)
        plan = build_bootstrap_plan(host, lock)
    except ManifestError as exc:
        return _emit([ValidationIssue("bootstrap", str(exc))], None, args.json)
    if not args.apply:
        payload = [action.to_dict() for action in plan]
        if args.json:
            print(json.dumps({"ok": True, "mode": "plan", "actions": payload}, indent=2))
        elif not plan:
            print("No bootstrap actions required.")
        else:
            print("Bootstrap plan (no changes made):")
            for action in plan:
                command = " ".join(action.command) if action.command else "internal pinned download"
                print(f"- {action.description}: {command}")
        return 0
    try:
        installed = apply_bootstrap(
            host,
            args.tools_lock,
            capture_checksums=args.capture_checksums,
            install_system=not args.skip_system,
            install_tools=not args.skip_pinned_tools,
        )
    except (ManifestError, OSError, subprocess.SubprocessError) as exc:
        return _emit([ValidationIssue("bootstrap", str(exc))], None, args.json)
    report = [
        {
            "name": tool.name,
            "archive": str(tool.archive),
            "install_dir": str(tool.install_dir),
            "sha256": tool.sha256,
        }
        for tool in installed
    ]
    if args.json:
        print(json.dumps({"ok": True, "mode": "apply", "installed": report}, indent=2))
    else:
        print("Bootstrap completed.")
        for tool in report:
            print(f"- {tool['name']}: {tool['install_dir']} sha256={tool['sha256']}")
    return 0


def _run_stage(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        products = manifest.get("products")
        if not isinstance(products, dict) or args.product not in products:
            raise StageError(f"unknown product: {args.product}")
        host = load_host_config(args.host, args.repo_root)
        command = list(args.stage_command)
        if command and command[0] == "--":
            command = command[1:]
        runner = StageRunner(host.paths.work_root)
        result = runner.run(
            product=args.product,
            stage=args.stage,
            command=command,
            build_id=args.build_id,
            expected_outputs=args.output,
            resume=not args.no_resume,
            resume_key=args.resume_key,
            metadata={
                "manifest": str(args.manifest),
                "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            },
        )
    except (ManifestError, StageError) as exc:
        return _emit([ValidationIssue("run-stage", str(exc))], None, args.json)
    payload = result.to_dict()
    if args.json:
        print(json.dumps({"ok": result.status in {"success", "skipped"}, "result": payload}, indent=2))
    else:
        print(
            f"{result.status.upper()} build={result.build_id} "
            f"stage={result.stage} attempt={result.attempt_id} exit={result.exit_code}"
        )
        print(f"stdout: {result.stdout_log}")
        print(f"stderr: {result.stderr_log}")
    return 0 if result.status in {"success", "skipped"} else 1


def _show_build(args: argparse.Namespace) -> int:
    try:
        host = load_host_config(args.host, args.repo_root)
        history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
        build = history.get_build(args.build_id)
        if build is None:
            raise StageError(f"unknown build id: {args.build_id}")
        attempts = history.attempts(args.build_id)
    except (ManifestError, StageError) as exc:
        return _emit([ValidationIssue("show-build", str(exc))], None, args.json)
    payload = {"build": build, "attempts": attempts}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uralla-build")
    parser.add_argument("--manifest", default=Path("config/maps.yaml"), type=Path)
    parser.add_argument("--host", default=Path("config/host.yaml"), type=Path)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("validate-manifest")
    manifest_parser.set_defaults(handler=_validate_manifest)

    areas_parser = subparsers.add_parser("validate-areas")
    areas_parser.add_argument("product")
    areas_parser.add_argument("areas", type=Path)
    areas_parser.add_argument("--template", type=Path)
    areas_parser.set_defaults(handler=_validate_areas)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--repo-root", default=Path("."), type=Path)
    doctor_parser.add_argument("--tools-lock", default=Path("config/tools.lock.yaml"), type=Path)
    doctor_parser.add_argument("--skip-tools", action="store_true", help="skip executable checks")
    doctor_parser.add_argument("--skip-data", action="store_true", help="skip external data checks")
    doctor_parser.add_argument("--skip-publish-probe", action="store_true")
    doctor_parser.set_defaults(handler=_doctor)

    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_parser.add_argument("--repo-root", default=Path("."), type=Path)
    bootstrap_parser.add_argument("--tools-lock", default=Path("config/tools.lock.yaml"), type=Path)
    bootstrap_parser.add_argument("--apply", action="store_true", help="execute the displayed plan")
    bootstrap_parser.add_argument(
        "--capture-checksums",
        action="store_true",
        help="capture first-download SHA-256 values into the lock file",
    )
    bootstrap_parser.add_argument("--skip-system", action="store_true")
    bootstrap_parser.add_argument("--skip-pinned-tools", action="store_true")
    bootstrap_parser.set_defaults(handler=_bootstrap)

    stage_parser = subparsers.add_parser("run-stage")
    stage_parser.add_argument("product")
    stage_parser.add_argument("stage")
    stage_parser.add_argument("--repo-root", default=Path("."), type=Path)
    stage_parser.add_argument("--build-id")
    stage_parser.add_argument(
        "--output",
        action="append",
        default=[],
        help="expected non-empty output relative to the stage workspace; repeatable",
    )
    stage_parser.add_argument("--resume-key")
    stage_parser.add_argument("--no-resume", action="store_true")
    stage_parser.add_argument(
        "stage_command",
        nargs="+",
        help="argv to execute; put -- before command options",
    )
    stage_parser.set_defaults(handler=_run_stage)

    show_parser = subparsers.add_parser("show-build")
    show_parser.add_argument("build_id")
    show_parser.add_argument("--repo-root", default=Path("."), type=Path)
    show_parser.set_defaults(handler=_show_build)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

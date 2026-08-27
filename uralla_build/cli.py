"""Command line entry point for build-system validation."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .bootstrap import apply_bootstrap, build_bootstrap_plan, load_tools_lock
from .build_plan import ProductBuildPlan, plan_product_build
from .errors import ManifestError, StageError, ValidationIssue
from .external_data import has_refresh_errors, refresh_supplemental_data
from .doctor import has_errors, run_doctor
from .dem import select_dem_files, write_selection
from .history import HistoryStore
from .host import load_host_config, validate_host_config
from .manifest import load_manifest, validate_manifest
from .pipeline import PipelineRunner, PipelineStage
from .publish import publication_targets, publish_product
from .preprocessor import preprocess_pbf
from .ranges import validate_generated_range
from .runner import StageRunner
from .scheduler import build_queue, next_due_product


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


def _refresh_data(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        host = load_host_config(args.host, args.repo_root)
        results = refresh_supplemental_data(manifest, host)
    except (ManifestError, OSError) as exc:
        return _emit([ValidationIssue("refresh-data", str(exc))], None, args.json)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not has_refresh_errors(results),
                    "results": [result.to_dict() for result in results],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for result in results:
            print(f"{result.status.upper():7} {result.name}: {result.target} — {result.detail}")
    return 1 if has_refresh_errors(results) else 0


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


def _select_dem(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        selection = select_dem_files(
            manifest,
            args.inventory,
            args.repo_root,
            halo=args.halo,
        )
        write_selection(selection, args.output, args.exact_output, args.report)
    except (ManifestError, OSError) as exc:
        return _emit([ValidationIssue("select-dem", str(exc))], None, args.json)
    summary = {
        "elevation_products": len(selection.elevation_products),
        "polygons": len(selection.polygons),
        "inventory_hgt_files": selection.inventory_hgt_files,
        "inventory_hgt_bytes": selection.inventory_hgt_bytes,
        "exact_tiles": selection.exact_tiles,
        "exact_files": len(selection.exact_files),
        "exact_bytes": selection.exact_bytes,
        "halo": selection.halo,
        "selected_files": len(selection.selected_files),
        "selected_bytes": selection.selected_bytes,
        "intersecting_tiles_without_file": len(selection.intersecting_tiles_without_file),
        "output": str(args.output),
        "exact_output": str(args.exact_output),
        "report": str(args.report),
    }
    if args.json:
        print(json.dumps({"ok": True, "report": summary}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _queue(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        issues = validate_manifest(manifest)
        if issues:
            return _emit(issues, None, args.json)
        host = load_host_config(args.host, args.repo_root)
        history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
        items = build_queue(
            manifest,
            history.latest_success_by_product(),
            history.running_products(),
        )
        next_item = next_due_product(items)
    except ManifestError as exc:
        return _emit([ValidationIssue("queue", str(exc))], None, args.json)
    payload = {
        "next": next_item.to_dict() if next_item else None,
        "items": [item.to_dict() for item in items],
    }
    if args.json:
        print(json.dumps({"ok": True, "report": payload}, ensure_ascii=False, indent=2))
    else:
        print(f"NEXT {next_item.product}" if next_item else "NEXT none")
        for item in items:
            state = "due" if item.due else "waiting"
            age = "never" if item.never_built else f"{(item.overdue_seconds or 0) / 86400:.2f}d"
            print(f"{item.priority:5} {state:7} {age:>10} {item.product}")
    return 0


def _publish(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        products = manifest.get("products")
        if not isinstance(products, dict) or not isinstance(products.get(args.product), dict):
            raise StageError(f"unknown product: {args.product}")
        host = load_host_config(args.host, args.repo_root)
        product = products[args.product]
        targets = publication_targets(host, product, args.img, args.gmapi)
        if not args.apply:
            payload: object = {
                "mode": "plan",
                "targets": [asdict(target) for target in targets],
            }
        else:
            artifacts = publish_product(host, product, args.img, args.gmapi)
            payload = {
                "mode": "apply",
                "artifacts": [artifact.to_dict() for artifact in artifacts],
            }
    except (ManifestError, StageError, OSError) as exc:
        return _emit([ValidationIssue("publish", str(exc))], None, args.json)
    if args.json:
        print(json.dumps({"ok": True, "report": payload}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _build_product(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        issues = validate_manifest(manifest)
        if issues:
            return _emit(issues, None, args.json)
        host = load_host_config(args.host, args.repo_root)
        host_issues = validate_host_config(host)
        if host_issues:
            return _emit(host_issues, None, args.json)
        lock = load_tools_lock(args.tools_lock)
        products = manifest.get("products")
        if not isinstance(products, dict) or not isinstance(products.get(args.product), dict):
            raise StageError(f"unknown product: {args.product}")
        product = products[args.product]

        if not args.apply:
            plan = plan_product_build(
                manifest,
                host,
                lock,
                product_key=args.product,
                build_id=args.build_id or "PLAN",
                repo_root=args.repo_root,
                manifest_path=args.manifest,
                build_date=date.today(),
            )
            targets = publication_targets(
                host, product, plan.img_source, plan.gmapi_source
            )
            payload: object = {
                "mode": "plan",
                "plan": plan.to_dict(),
                "targets": [asdict(target) for target in targets],
            }
            status = 0
        else:
            runner = StageRunner(host.paths.work_root)
            pipeline = PipelineRunner(runner)
            selected: dict[str, ProductBuildPlan] = {}

            def stages(build_id: str) -> tuple[PipelineStage, ...]:
                build = runner.history.get_build(build_id)
                if build is None:
                    raise StageError(f"unknown build id: {build_id}")
                created = date.fromisoformat(str(build["created_at"])[:10])
                selected["plan"] = plan_product_build(
                    manifest,
                    host,
                    lock,
                    product_key=args.product,
                    build_id=build_id,
                    repo_root=args.repo_root,
                    manifest_path=args.manifest,
                    build_date=created,
                )
                return selected["plan"].stages

            def finalize(_build_id: str) -> object:
                plan = selected["plan"]
                artifacts = publish_product(
                    host,
                    product,
                    plan.img_source,
                    plan.gmapi_source,
                )
                return [artifact.to_dict() for artifact in artifacts]

            result = pipeline.run(
                product=args.product,
                stages=stages,
                build_id=args.build_id,
                metadata={
                    "manifest": str(args.manifest),
                    "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                },
                resume=not args.no_resume,
                finalize=finalize,
            )
            payload = {"mode": "apply", "result": result.to_dict()}
            status = 0 if result.status == "success" else 1
    except (ManifestError, StageError, OSError, ValueError) as exc:
        return _emit([ValidationIssue("build-product", str(exc))], None, args.json)

    if args.json:
        print(json.dumps({"ok": status == 0, "report": payload}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return status


def _preprocess(args: argparse.Namespace) -> int:
    try:
        report = preprocess_pbf(
            args.input,
            args.output,
            args.config,
            args.profile,
            args.report,
        )
    except (StageError, OSError) as exc:
        return _emit([ValidationIssue("preprocess", str(exc))], None, args.json)
    if args.json:
        print(json.dumps({"ok": True, "report": report}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
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

    refresh_parser = subparsers.add_parser("refresh-data")
    refresh_parser.add_argument("--repo-root", default=Path("."), type=Path)
    refresh_parser.set_defaults(handler=_refresh_data)

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

    dem_parser = subparsers.add_parser("select-dem")
    dem_parser.add_argument("--repo-root", default=Path("."), type=Path)
    dem_parser.add_argument("--inventory", default=Path("dem-files.tsv"), type=Path)
    dem_parser.add_argument("--halo", default=1, type=int)
    dem_parser.add_argument("--output", default=Path("config/dem-required-files.txt"), type=Path)
    dem_parser.add_argument(
        "--exact-output", default=Path("config/dem-required-files-exact.txt"), type=Path
    )
    dem_parser.add_argument("--report", default=Path("config/dem-selection-report.json"), type=Path)
    dem_parser.set_defaults(handler=_select_dem)

    queue_parser = subparsers.add_parser("queue")
    queue_parser.add_argument("--repo-root", default=Path("."), type=Path)
    queue_parser.set_defaults(handler=_queue)

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("product")
    publish_parser.add_argument("--repo-root", default=Path("."), type=Path)
    publish_parser.add_argument("--img", required=True, type=Path)
    publish_parser.add_argument("--gmapi", required=True, type=Path)
    publish_parser.add_argument("--apply", action="store_true")
    publish_parser.set_defaults(handler=_publish)

    product_parser = subparsers.add_parser("build-product")
    product_parser.add_argument("product")
    product_parser.add_argument("--repo-root", default=Path("."), type=Path)
    product_parser.add_argument(
        "--tools-lock", default=Path("config/tools.lock.yaml"), type=Path
    )
    product_parser.add_argument("--build-id")
    product_parser.add_argument("--no-resume", action="store_true")
    product_parser.add_argument(
        "--apply", action="store_true", help="execute stages and publish the release"
    )
    product_parser.set_defaults(handler=_build_product)

    preprocess_parser = subparsers.add_parser("preprocess")
    preprocess_parser.add_argument("--input", required=True, type=Path)
    preprocess_parser.add_argument("--output", required=True, type=Path)
    preprocess_parser.add_argument(
        "--config", default=Path("config/preprocessor-blacklist.yaml"), type=Path
    )
    preprocess_parser.add_argument(
        "--profile", required=True, action="append", help="blacklist profile; repeatable"
    )
    preprocess_parser.add_argument("--report", required=True, type=Path)
    preprocess_parser.set_defaults(handler=_preprocess)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

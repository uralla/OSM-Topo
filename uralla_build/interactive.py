"""Interactive terminal launcher for Garmin map builds.

This module is deliberately a thin UI over the existing manifest, history and
CLI commands. It does not implement a second build system.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import shlex
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

from .errors import ManifestError
from .history import HistoryStore
from .host import load_host_config
from .manifest import load_manifest
from .public_status import render_map_update_status
from .scheduler import build_queue
from .service_control import (
    SERVICE_NAME,
    run_service_action,
    run_service_log,
    run_service_status,
    service_state,
)


_WIDTH = 92


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _local_time(value: object) -> str:
    stamp = _parse_time(value)
    if stamp is None:
        return "—"
    return stamp.astimezone().strftime("%d.%m.%Y %H:%M")


def _age(value: object) -> str:
    stamp = _parse_time(value)
    if stamp is None:
        return "never"
    now = datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    seconds = max((now - stamp.astimezone(timezone.utc)).total_seconds(), 0.0)
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def _duration(seconds: object) -> str:
    try:
        total = max(int(round(float(seconds or 0))), 0)
    except (TypeError, ValueError):
        return "—"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _products(manifest: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw = manifest.get("products")
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): value for key, value in raw.items() if isinstance(value, Mapping)}


def _display_name(key: str, product: Mapping[str, object]) -> str:
    names = product.get("names")
    if isinstance(names, Mapping):
        family = names.get("family")
        if family:
            return str(family)
    return key


def _latest_builds(history: HistoryStore) -> dict[str, dict[str, Any]]:
    with history.connect() as connection:
        rows = connection.execute(
            """SELECT b.* FROM builds b
               JOIN (
                   SELECT product, MAX(created_at) AS created_at
                   FROM builds GROUP BY product
               ) latest
               ON latest.product = b.product AND latest.created_at = b.created_at"""
        ).fetchall()
    return {str(row["product"]): dict(row) for row in rows}


def _ordered_products(
    manifest: Mapping[str, object], history: HistoryStore
) -> list[tuple[str, Mapping[str, object], dict[str, Any] | None]]:
    products = _products(manifest)
    latest = _latest_builds(history)
    items = [(key, product, latest.get(key)) for key, product in products.items()]
    items.sort(
        key=lambda item: (
            str((item[2] or {}).get("created_at", "")),
            item[0],
        ),
        reverse=True,
    )
    return items


def _queue_state(manifest: Mapping[str, object], history: HistoryStore) -> dict[str, str]:
    try:
        queue = build_queue(
            manifest,
            history.latest_success_by_product(),
            history.running_products(),
        )
    except Exception:
        return {}
    result: dict[str, str] = {}
    running = history.running_products()
    for item in queue:
        if item.product in running:
            result[item.product] = "RUNNING"
        elif item.never_built:
            result[item.product] = "NEW"
        elif item.due:
            result[item.product] = "STALE"
        else:
            result[item.product] = "OK"
    return result


def _header(title: str) -> None:
    print("\n" + "═" * _WIDTH)
    print(f"  {title}")
    print("═" * _WIDTH)


def _show_products(manifest: Mapping[str, object], history: HistoryStore) -> list[str]:
    _header("GARMIN OSM TOPO — MAPS")
    items = _ordered_products(manifest, history)
    states = _queue_state(manifest, history)
    print(f"  {'#':>2}  {'Map':<28} {'State':<10} {'Last build':<17} {'Age':>6}  {'Result':<11}")
    print("  " + "─" * (_WIDTH - 4))
    keys: list[str] = []
    for index, (key, product, build) in enumerate(items, 1):
        keys.append(key)
        status = str((build or {}).get("status", "never")).upper()
        last = _local_time((build or {}).get("finished_at") or (build or {}).get("created_at"))
        age = _age((build or {}).get("finished_at") or (build or {}).get("created_at"))
        print(
            f"  {index:>2}. {_display_name(key, product):<28.28} "
            f"{states.get(key, '—'):<10} {last:<17} {age:>6}  {status:<11}"
        )
    print("  " + "─" * (_WIDTH - 4))
    print("  s  map status    d  daemon    u  update from GitHub    a  add map    q  quit")
    return keys


def _show_map_status(manifest: Mapping[str, object], history: HistoryStore) -> None:
    _header("MAP UPDATE STATUS")
    print(render_map_update_status(manifest, history).rstrip())
    input("\nPress Enter to return…")


def _daemon_menu(repo_root: Path) -> None:
    while True:
        state = service_state()
        _header("DAEMON")
        print(f"  Service: {SERVICE_NAME}")
        print(f"  State:   {state.state}")
        if not state.available:
            print("\n  systemd/systemctl is not available on this host.")
            input("\nPress Enter to return…")
            return
        if not state.installed:
            print("\n  Service is not installed.")
            print(f"  Install: {repo_root / 'scripts' / 'install-daemon-service.sh'}")
            input("\nPress Enter to return…")
            return

        print("\n  1. Start")
        print("  2. Stop")
        print("  3. Restart")
        print("  4. Status")
        print("  5. Show recent log")
        print("  6. Follow log")
        print("  0. Back")
        choice = input("\nSelect: ").strip().lower()
        if choice in {"0", "q", ""}:
            return
        if choice in {"1", "2", "3"}:
            action = {"1": "start", "2": "stop", "3": "restart"}[choice]
            code = run_service_action(action)
            print(f"\n{action} finished with exit code {code}.")
            input("Press Enter…")
        elif choice == "4":
            print()
            run_service_status()
            input("\nPress Enter…")
        elif choice == "5":
            print()
            run_service_log()
            input("\nPress Enter…")
        elif choice == "6":
            print("\nFollowing daemon log; Ctrl+C returns to this menu.\n")
            try:
                run_service_log(follow=True)
            except KeyboardInterrupt:
                print()


def _git_head(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _update_repository(repo_root: Path, host_path: Path, manifest_path: Path) -> None:
    _header("UPDATE FROM GITHUB")
    print(f"  Repository: {repo_root}")
    print("  Command:    git pull --ff-only\n")
    before = _git_head(repo_root)
    try:
        completed = subprocess.run(["git", "pull", "--ff-only"], cwd=repo_root)
    except KeyboardInterrupt:
        print("\nUpdate interrupted.")
        input("Press Enter to return…")
        return
    if completed.returncode != 0:
        print(f"\nGit update failed with exit code {completed.returncode}.")
        input("Press Enter to return…")
        return

    after = _git_head(repo_root)
    if before is not None and before == after:
        print("\nRepository is already up to date.")
        input("Press Enter to return…")
        return

    if before and after:
        print(f"\nUpdated: {before[:12]} -> {after[:12]}")
    else:
        print("\nRepository updated.")
    print("Restarting the menu so the new code is loaded…")
    try:
        os.chdir(repo_root)
        os.execv(
            sys.executable,
            [
                sys.executable,
                "-m",
                "uralla_build",
                "--manifest",
                str(manifest_path),
                "--host",
                str(host_path),
            ],
        )
    except OSError as exc:
        print(f"\nRepository was updated, but automatic restart failed: {exc}")
        print("Exit and run ./start again to load the new code.")
        input("Press Enter to return…")


def _command(repo_root: Path, host_path: Path, manifest_path: Path, product: str, *, from_stage: str | None = None) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "uralla_build",
        "--manifest",
        str(manifest_path),
        "--host",
        str(host_path),
        "build-product",
        product,
        "--repo-root",
        str(repo_root),
    ]
    if from_stage is not None:
        command.extend(("--from-stage", from_stage))
    command.append("--apply")
    return command


def _run(command: list[str], repo_root: Path) -> int:
    print("\nCommand:")
    print("  " + shlex.join(command))
    answer = input("\nEnter = run, 0 = cancel: ").strip().lower()
    if answer == "0":
        return 0
    print()
    try:
        completed = subprocess.run(command, cwd=repo_root)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    print(f"\nCommand finished with exit code {completed.returncode}.")
    input("Press Enter to return to the map menu…")
    return int(completed.returncode)


def _stage_duration(attempts: list[dict[str, Any]], stage_name: str) -> str:
    total = sum(
        float(a.get("duration_seconds") or 0.0)
        for a in attempts
        if a.get("stage_name") == stage_name
        and a.get("status") in {"success", "failed", "interrupted", "skipped"}
    )
    return _duration(total) if total > 0 else "—"


def _history_detail(history: HistoryStore, build: Mapping[str, object]) -> None:
    build_id = str(build["build_id"])
    attempts = history.attempts(build_id)
    terminal_attempts = [
        attempt
        for attempt in attempts
        if attempt.get("status") in {"success", "failed", "interrupted", "skipped"}
    ]
    total = sum(float(a.get("duration_seconds") or 0.0) for a in terminal_attempts)
    finished = build["finished_at"] or build["created_at"]

    _header(f"BUILD — {build_id[:12]}")
    print(f"  Date:   {_local_time(finished)}")
    print(f"  Status: {str(build['status']).upper()}")
    print(f"  Total:  {_duration(total)}")
    print(f"  ID:     {build_id}")
    print("\n  Stages")
    print("  " + "─" * (_WIDTH - 4))
    for attempt in terminal_attempts:
        marker = " ↺" if attempt.get("status") == "skipped" else ""
        print(
            f"  {str(attempt.get('stage_name')):<24} "
            f"{str(attempt.get('status')).upper():<12} "
            f"{_duration(attempt.get('duration_seconds')):>9}{marker}"
        )
    error = next(
        (str(a.get("error")) for a in reversed(attempts) if a.get("error")),
        "",
    )
    if error:
        print(f"\n  ERROR: {error}")
    input("\n0 = back: ")


def _history(history: HistoryStore, product: str) -> None:
    while True:
        _header(f"HISTORY — {product}")
        with history.connect() as connection:
            builds = connection.execute(
                """SELECT * FROM builds WHERE product = ?
                   ORDER BY created_at DESC LIMIT 12""",
                (product,),
            ).fetchall()
        if not builds:
            print("  No builds yet.")
            input("\n0 = back: ")
            return

        print(
            f"  {'#':>2}  {'Date':<17} {'Status':<10} {'Total':>8} "
            f"{'Preprocess':>10} {'Splitter':>9} {'mkgmap':>8}"
        )
        print("  " + "─" * (_WIDTH - 4))
        build_rows: list[dict[str, object]] = []
        for index, build in enumerate(builds, 1):
            build_dict = dict(build)
            build_rows.append(build_dict)
            attempts = history.attempts(str(build["build_id"]))
            terminal_attempts = [
                attempt
                for attempt in attempts
                if attempt.get("status") in {"success", "failed", "interrupted", "skipped"}
            ]
            total = sum(float(a.get("duration_seconds") or 0.0) for a in terminal_attempts)
            finished = build["finished_at"] or build["created_at"]
            print(
                f"  {index:>2}. {_local_time(finished):<17} "
                f"{str(build['status']).upper():<10} {_duration(total):>8} "
                f"{_stage_duration(terminal_attempts, 'preprocess'):>10} "
                f"{_stage_duration(terminal_attempts, 'splitter'):>9} "
                f"{_stage_duration(terminal_attempts, 'mkgmap'):>8}"
            )

        print("  " + "─" * (_WIDTH - 4))
        print("  Select build number for details, 0 = back")
        choice = input("\nSelect: ").strip()
        if choice in {"0", ""}:
            return
        try:
            selected = int(choice) - 1
        except ValueError:
            continue
        if 0 <= selected < len(build_rows):
            _history_detail(history, build_rows[selected])


def _product_menu(
    manifest: Mapping[str, object],
    history: HistoryStore,
    key: str,
    repo_root: Path,
    host_path: Path,
    manifest_path: Path,
) -> None:
    product = _products(manifest)[key]
    while True:
        _header(_display_name(key, product))
        latest = _latest_builds(history).get(key)
        if latest:
            print(
                f"  Last: {_local_time(latest.get('finished_at') or latest.get('created_at'))}  "
                f"status={str(latest.get('status')).upper()}  build={latest.get('build_id')}"
            )
        else:
            print("  No previous builds.")
        print("\n  1. Full build")
        print("  2. Continue from splitter (reuse latest merge checkpoint)")
        print("  3. mkgmap only (reuse prepared splitter data)")
        print("  4. History / stage timings")
        print("  5. Edit map configuration  [next GUI phase]")
        print("  6. Delete map configuration [next GUI phase]")
        print("  0. Back")
        choice = input("\nSelect: ").strip().lower()
        if choice == "1":
            _run(_command(repo_root, host_path, manifest_path, key), repo_root)
        elif choice == "2":
            _run(_command(repo_root, host_path, manifest_path, key, from_stage="splitter"), repo_root)
        elif choice == "3":
            _run(_command(repo_root, host_path, manifest_path, key, from_stage="mkgmap"), repo_root)
        elif choice == "4":
            _history(history, key)
        elif choice in {"5", "6"}:
            print("\nThis editor is the next GUI phase; build actions are already active.")
            input("Press Enter…")
        elif choice in {"0", "q", ""}:
            return


def run_interactive(
    *,
    repo_root: str | Path = ".",
    manifest_path: str | Path = "config/maps.yaml",
    host_path: str | Path = "config/host.yaml",
) -> int:
    """Run the zero-argument interactive launcher."""

    repo = Path(repo_root).resolve()
    manifest_file = (repo / manifest_path).resolve() if not Path(manifest_path).is_absolute() else Path(manifest_path)
    host_file = (repo / host_path).resolve() if not Path(host_path).is_absolute() else Path(host_path)
    try:
        manifest = load_manifest(manifest_file)
        host = load_host_config(host_file, repo)
    except (ManifestError, OSError) as exc:
        print(f"ERROR GUI: {exc}", file=sys.stderr)
        return 1
    history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")

    while True:
        keys = _show_products(manifest, history)
        choice = input("\nSelect map: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            return 0
        if choice == "s":
            _show_map_status(manifest, history)
            continue
        if choice == "d":
            _daemon_menu(repo)
            continue
        if choice == "u":
            _update_repository(repo, host_file, manifest_file)
            continue
        if choice == "a":
            print("\nMap editor/add wizard is the next GUI phase.")
            input("Press Enter…")
            continue
        try:
            index = int(choice) - 1
        except ValueError:
            continue
        if 0 <= index < len(keys):
            _product_menu(manifest, history, keys[index], repo, host_file, manifest_file)

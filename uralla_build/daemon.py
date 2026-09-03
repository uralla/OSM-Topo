"""Long-running scheduler for unattended Garmin product builds."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Iterator, Mapping

from .errors import ManifestError, StageError
from .history import HistoryStore, utc_now
from .host import load_host_config
from .manifest import load_manifest, validate_manifest
from .public_status import write_map_update_status
from .scheduler import QueueItem, build_queue


DEFAULT_IDLE_SECONDS = 300.0
DEFAULT_FAILURE_RETRY_SECONDS = 900.0
ACTIVE_POLL_SECONDS = 1.0


def _log(message: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[daemon {stamp}] {message}", flush=True)


@contextmanager
def _exclusive_lock(path: Path, description: str) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise StageError(f"another {description} holds {path}") from exc
            raise
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _pipeline_is_idle(work_root: Path) -> bool:
    path = work_root / "state" / "pipeline.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                return False
            raise
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return True
    finally:
        handle.close()


def _interrupt_running_builds(history: HistoryStore, reason: str) -> int:
    """Close stale DB state only when the caller has proved no pipeline is active."""

    finished_at = utc_now()
    with history.connect() as connection:
        rows = connection.execute(
            "SELECT build_id FROM builds WHERE status = 'running'"
        ).fetchall()
        build_ids = [str(row["build_id"]) for row in rows]
        if not build_ids:
            return 0
        for build_id in build_ids:
            connection.execute(
                """UPDATE stage_attempts
                   SET status = 'interrupted', finished_at = ?, exit_code = 130, error = ?
                   WHERE build_id = ? AND status = 'running'""",
                (finished_at, reason, build_id),
            )
            connection.execute(
                """UPDATE builds SET status = 'interrupted', finished_at = ?
                   WHERE build_id = ? AND status = 'running'""",
                (finished_at, build_id),
            )
        return len(build_ids)


def _recover_if_idle(history: HistoryStore, work_root: Path, reason: str) -> int:
    if not history.running_products() or not _pipeline_is_idle(work_root):
        return 0
    return _interrupt_running_builds(history, reason)


def _select_due(
    items: list[QueueItem],
    retry_not_before: dict[str, float],
    now_monotonic: float,
    excluded: set[str] | None = None,
) -> QueueItem | None:
    skipped = excluded or set()
    return next(
        (
            item
            for item in items
            if item.product not in skipped
            and item.due
            and retry_not_before.get(item.product, 0.0) <= now_monotonic
        ),
        None,
    )


def _sleep_timeout(
    items: list[QueueItem],
    retry_not_before: dict[str, float],
    now_monotonic: float,
    idle_seconds: float,
) -> float:
    blocked = [
        retry_not_before[item.product] - now_monotonic
        for item in items
        if item.due and retry_not_before.get(item.product, 0.0) > now_monotonic
    ]
    if blocked:
        return max(1.0, min(idle_seconds, min(blocked)))
    return idle_seconds


def _build_command(
    *,
    repo_root: Path,
    manifest_path: Path,
    host_path: Path,
    tools_lock_path: Path,
    product: str,
) -> list[str]:
    return [
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
        "--tools-lock",
        str(tools_lock_path),
        "--apply",
    ]


def _interrupt_children(children: Mapping[str, subprocess.Popen[bytes]]) -> None:
    for child in children.values():
        if child.poll() is not None:
            continue
        try:
            os.killpg(child.pid, signal.SIGINT)
        except ProcessLookupError:
            pass


def run_daemon(
    *,
    repo_root: Path,
    manifest_path: Path,
    host_path: Path,
    tools_lock_path: Path,
    idle_seconds: float = DEFAULT_IDLE_SECONDS,
    failure_retry_seconds: float = DEFAULT_FAILURE_RETRY_SECONDS,
    once: bool = False,
) -> int:
    repo_root = repo_root.resolve()
    manifest_path = manifest_path.resolve()
    host_path = host_path.resolve()
    tools_lock_path = tools_lock_path.resolve()
    host = load_host_config(host_path, repo_root)
    history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
    daemon_lock = host.paths.work_root / "state" / "daemon.lock"
    stop_event = threading.Event()
    children: dict[str, subprocess.Popen[bytes]] = {}
    retry_not_before: dict[str, float] = {}
    once_started = False
    once_exit: int | None = None
    last_running_snapshot: frozenset[str] = frozenset()

    def publish_status(manifest: Mapping[str, object]) -> None:
        try:
            target = write_map_update_status(manifest, host)
        except (OSError, ValueError, ManifestError) as exc:
            _log(f"cannot update public status table: {exc}")
        else:
            _log(f"public status updated: {target}")

    def request_stop(signum: int, _frame: object) -> None:
        if not stop_event.is_set():
            _log(
                f"received signal {signum}; interrupting {len(children)} active product(s)"
            )
        stop_event.set()
        _interrupt_children(children)

    previous_term = signal.signal(signal.SIGTERM, request_stop)
    previous_int = signal.signal(signal.SIGINT, request_stop)
    try:
        with _exclusive_lock(daemon_lock, "build daemon"):
            recovered = _recover_if_idle(
                history,
                host.paths.work_root,
                "recovered by daemon startup after previous process stopped",
            )
            if recovered:
                _log(f"recovered {recovered} stale running build(s) as interrupted")
            elif history.running_products():
                _log("active product pipeline detected; stale-build recovery deferred")

            _log(
                "started; light product slots="
                f"{host.preprocess_concurrency}; splitter/mkgmap phase=exclusive"
            )
            while True:
                # Reap finished children first so their slots are immediately reusable.
                for product, child in list(children.items()):
                    exit_code = child.poll()
                    if exit_code is None:
                        continue
                    del children[product]
                    if exit_code == 0:
                        retry_not_before.pop(product, None)
                        _log(f"product {product} completed successfully")
                    else:
                        retry_not_before[product] = time.monotonic() + failure_retry_seconds
                        _log(
                            f"product {product} failed with exit {exit_code}; "
                            f"retry in {int(failure_retry_seconds)}s"
                        )
                    if once_started:
                        once_exit = int(exit_code)

                if stop_event.is_set():
                    if children:
                        _interrupt_children(children)
                        time.sleep(0.1)
                        continue
                    _log("stopped")
                    return 0

                if once_started and not children:
                    return int(once_exit or 0)

                # Never run stale-build recovery while children owned by this daemon
                # are alive: pipelines briefly release their shared lock while
                # upgrading to the exclusive splitter/mkgmap phase.
                if not children:
                    recovered = _recover_if_idle(
                        history,
                        host.paths.work_root,
                        "recovered by daemon after abandoned product pipeline",
                    )
                    if recovered:
                        _log(f"recovered {recovered} stale running build(s) as interrupted")

                try:
                    manifest = load_manifest(manifest_path)
                    issues = validate_manifest(manifest)
                    if issues:
                        raise ManifestError("; ".join(str(issue) for issue in issues))
                    running_products = history.running_products()
                    items = build_queue(
                        manifest,
                        history.latest_success_by_product(),
                        running_products,
                    )
                except (ManifestError, OSError) as exc:
                    _log(f"scheduler error: {exc}")
                    if once and not children:
                        return 1
                    if children:
                        time.sleep(ACTIVE_POLL_SECONDS)
                    else:
                        stop_event.wait(failure_retry_seconds)
                    continue

                running_snapshot = frozenset(running_products)
                if running_snapshot != last_running_snapshot:
                    publish_status(manifest)
                    last_running_snapshot = running_snapshot

                active_products = set(children)
                launched = False
                max_children = 1 if once else host.preprocess_concurrency
                while len(children) < max_children and not once_started:
                    item = _select_due(
                        items,
                        retry_not_before,
                        time.monotonic(),
                        excluded=active_products,
                    )
                    if item is None:
                        break
                    command = _build_command(
                        repo_root=repo_root,
                        manifest_path=manifest_path,
                        host_path=host_path,
                        tools_lock_path=tools_lock_path,
                        product=item.product,
                    )
                    try:
                        child = subprocess.Popen(
                            command,
                            cwd=repo_root,
                            start_new_session=True,
                        )
                    except OSError as exc:
                        _log(f"cannot start product {item.product}: {exc}")
                        retry_not_before[item.product] = (
                            time.monotonic() + failure_retry_seconds
                        )
                        active_products.add(item.product)
                        continue
                    children[item.product] = child
                    active_products.add(item.product)
                    launched = True
                    _log(
                        f"starting product {item.product}; active slots "
                        f"{len(children)}/{max_children}"
                    )
                    if once:
                        once_started = True
                        break

                if launched:
                    publish_status(manifest)

                if children:
                    time.sleep(min(ACTIVE_POLL_SECONDS, idle_seconds))
                    continue

                if once:
                    _log("no due products")
                    return 0

                timeout = _sleep_timeout(
                    items,
                    retry_not_before,
                    time.monotonic(),
                    idle_seconds,
                )
                stop_event.wait(timeout)
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m uralla_build.daemon")
    parser.add_argument("--repo-root", default=Path("."), type=Path)
    parser.add_argument("--manifest", default=Path("config/maps.yaml"), type=Path)
    parser.add_argument("--host", default=Path("config/host.yaml"), type=Path)
    parser.add_argument("--tools-lock", default=Path("config/tools.lock.yaml"), type=Path)
    parser.add_argument("--idle-seconds", type=float, default=DEFAULT_IDLE_SECONDS)
    parser.add_argument(
        "--failure-retry-seconds", type=float, default=DEFAULT_FAILURE_RETRY_SECONDS
    )
    parser.add_argument("--once", action="store_true", help="build at most one due product")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.idle_seconds <= 0 or args.failure_retry_seconds <= 0:
        print("daemon sleep intervals must be positive", file=sys.stderr)
        return 2
    try:
        return run_daemon(
            repo_root=args.repo_root,
            manifest_path=args.manifest,
            host_path=args.host,
            tools_lock_path=args.tools_lock,
            idle_seconds=args.idle_seconds,
            failure_retry_seconds=args.failure_retry_seconds,
            once=args.once,
        )
    except (ManifestError, StageError, OSError) as exc:
        print(f"ERROR daemon: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
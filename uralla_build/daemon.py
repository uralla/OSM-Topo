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
from typing import Iterator

from .errors import ManifestError, StageError
from .history import HistoryStore
from .host import load_host_config
from .manifest import load_manifest, validate_manifest
from .scheduler import QueueItem, build_queue


DEFAULT_IDLE_SECONDS = 300.0
DEFAULT_FAILURE_RETRY_SECONDS = 900.0


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


def _select_due(
    items: list[QueueItem],
    retry_not_before: dict[str, float],
    now_monotonic: float,
) -> QueueItem | None:
    return next(
        (
            item
            for item in items
            if item.due and retry_not_before.get(item.product, 0.0) <= now_monotonic
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
        "uralla_build.entrypoint",
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
    child: subprocess.Popen[bytes] | None = None

    def request_stop(signum: int, _frame: object) -> None:
        nonlocal child
        if not stop_event.is_set():
            _log(f"received signal {signum}; stopping after current build interruption")
        stop_event.set()
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGINT)
            except ProcessLookupError:
                pass

    previous_term = signal.signal(signal.SIGTERM, request_stop)
    previous_int = signal.signal(signal.SIGINT, request_stop)
    try:
        with _exclusive_lock(daemon_lock, "build daemon"):
            if _pipeline_is_idle(host.paths.work_root):
                recovered = history.interrupt_running_builds(
                    "recovered by daemon startup after previous process stopped"
                )
                if recovered:
                    _log(f"recovered {recovered} stale running build(s) as interrupted")
            elif history.running_products():
                _log("active product pipeline detected; stale-build recovery deferred")

            retry_not_before: dict[str, float] = {}
            _log("started")
            while not stop_event.is_set():
                try:
                    manifest = load_manifest(manifest_path)
                    issues = validate_manifest(manifest)
                    if issues:
                        raise ManifestError("; ".join(str(issue) for issue in issues))
                    items = build_queue(
                        manifest,
                        history.latest_success_by_product(),
                        history.running_products(),
                    )
                except (ManifestError, OSError) as exc:
                    _log(f"scheduler error: {exc}")
                    if once:
                        return 1
                    stop_event.wait(failure_retry_seconds)
                    continue

                now = time.monotonic()
                item = _select_due(items, retry_not_before, now)
                if item is None:
                    if once:
                        _log("no due products")
                        return 0
                    timeout = _sleep_timeout(items, retry_not_before, now, idle_seconds)
                    stop_event.wait(timeout)
                    continue

                _log(f"starting product {item.product}")
                command = _build_command(
                    repo_root=repo_root,
                    manifest_path=manifest_path,
                    host_path=host_path,
                    tools_lock_path=tools_lock_path,
                    product=item.product,
                )
                try:
                    child = subprocess.Popen(command, cwd=repo_root, start_new_session=True)
                    exit_code = child.wait()
                except OSError as exc:
                    _log(f"cannot start product {item.product}: {exc}")
                    exit_code = 1
                finally:
                    child = None

                if stop_event.is_set():
                    _log("stopped")
                    return 0
                if exit_code == 0:
                    retry_not_before.pop(item.product, None)
                    _log(f"product {item.product} completed successfully")
                else:
                    retry_not_before[item.product] = time.monotonic() + failure_retry_seconds
                    _log(
                        f"product {item.product} failed with exit {exit_code}; "
                        f"retry in {int(failure_retry_seconds)}s"
                    )
                if once:
                    return 0 if exit_code == 0 else exit_code
            _log("stopped")
            return 0
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

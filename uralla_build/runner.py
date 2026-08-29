"""Cross-platform (Ubuntu/macOS) stage execution with durable checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import subprocess
import sys
import threading
import time
from typing import BinaryIO, Mapping, Sequence

from .errors import StageError
from .history import HistoryStore


NAME_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
HEARTBEAT_SECONDS = 30.0
POLL_SECONDS = 1.0
LIVE_OUTPUT_STAGES = frozenset({"preprocess", "prepare-tiles", "mkgmap"})


@dataclass(frozen=True, slots=True)
class StageResult:
    build_id: str
    attempt_id: int
    product: str
    stage: str
    status: str
    exit_code: int
    duration_seconds: float
    stdout_log: str
    stderr_log: str
    checkpoint: list[dict[str, object]] | None
    reused_attempt_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _relative_output(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        raise StageError(f"expected output must be a safe relative path: {value!r}")
    return path


def _directory_snapshot(path: Path) -> dict[str, int | str]:
    file_count = 0
    total_size = 0
    newest_mtime_ns = path.stat().st_mtime_ns
    for entry in path.rglob("*"):
        if entry.is_symlink():
            raise StageError(f"checkpoint output contains a symlink: {entry}")
        if entry.is_file():
            stat = entry.stat()
            file_count += 1
            total_size += stat.st_size
            newest_mtime_ns = max(newest_mtime_ns, stat.st_mtime_ns)
    if file_count == 0:
        raise StageError(f"checkpoint directory is empty: {path}")
    return {
        "kind": "directory",
        "file_count": file_count,
        "size": total_size,
        "mtime_ns": newest_mtime_ns,
    }


def snapshot_outputs(stage_root: Path, expected_outputs: Sequence[str]) -> list[dict[str, object]]:
    """Capture cheap but deterministic existence/size/mtime checkpoint metadata."""

    snapshot: list[dict[str, object]] = []
    for value in expected_outputs:
        relative = _relative_output(value)
        path = stage_root.joinpath(*relative.parts)
        if path.is_symlink():
            raise StageError(f"checkpoint output is a symlink: {path}")
        if path.is_file():
            stat = path.stat()
            if stat.st_size == 0:
                raise StageError(f"checkpoint file is empty: {path}")
            details: dict[str, object] = {
                "kind": "file",
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        elif path.is_dir():
            details = _directory_snapshot(path)
        else:
            raise StageError(f"checkpoint output is missing: {path}")
        snapshot.append({"path": relative.as_posix(), **details})
    return snapshot


def _resume_key(
    command: Sequence[str], environment: Mapping[str, str], expected_outputs: Sequence[str]
) -> str:
    payload = json.dumps(
        {
            "command": list(command),
            "environment": dict(sorted(environment.items())),
            "outputs": list(expected_outputs),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _usage_metrics(usage: object) -> dict[str, int | float]:
    peak = int(getattr(usage, "ru_maxrss"))
    if sys.platform == "darwin":
        peak //= 1024
    return {
        "cpu_user_seconds": float(getattr(usage, "ru_utime")),
        "cpu_system_seconds": float(getattr(usage, "ru_stime")),
        "peak_rss_kib": peak,
        "minor_faults": int(getattr(usage, "ru_minflt")),
        "major_faults": int(getattr(usage, "ru_majflt")),
        "swaps": int(getattr(usage, "ru_nswap")),
        "block_input_operations": int(getattr(usage, "ru_inblock")),
        "block_output_operations": int(getattr(usage, "ru_oublock")),
    }


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _format_elapsed(seconds: float) -> str:
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _tee_live_output(
    pipe: BinaryIO,
    log: BinaryIO,
    stage: str,
) -> None:
    """Copy one child stream to its durable log and the controlling terminal."""

    try:
        for raw_line in iter(pipe.readline, b""):
            log.write(raw_line)
            log.flush()
            text = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if text:
                print(f"[{stage}] {text}", file=sys.stderr, flush=True)
    finally:
        pipe.close()


def _wait_with_heartbeat(
    process: subprocess.Popen[bytes], stage: str, started: float
) -> tuple[int, object]:
    """Wait for one child while keeping the controlling terminal visibly alive."""

    next_heartbeat = started + HEARTBEAT_SECONDS
    while True:
        waited_pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if waited_pid == process.pid:
            return status, usage
        now = time.monotonic()
        if now >= next_heartbeat:
            print(
                f"[{stage}] running {_format_elapsed(now - started)}",
                file=sys.stderr,
                flush=True,
            )
            next_heartbeat = now + HEARTBEAT_SECONDS
        time.sleep(POLL_SECONDS)


class StageRunner:
    """Run one explicit argv command and persist every attempt immediately."""

    def __init__(self, work_root: str | Path):
        self.work_root = Path(work_root).resolve()
        self.builds_root = self.work_root / "builds"
        self.history = HistoryStore(self.work_root / "state" / "history.sqlite3")

    def create_build(self, product: str, metadata: Mapping[str, object] | None = None) -> str:
        if not NAME_RE.fullmatch(product):
            raise StageError(f"invalid product name: {product!r}")
        build_metadata: dict[str, object] = {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        }
        build_metadata.update(metadata or {})
        return self.history.create_build(product, build_metadata)

    def run(
        self,
        *,
        product: str,
        stage: str,
        command: Sequence[str],
        build_id: str | None = None,
        expected_outputs: Sequence[str] = (),
        environment: Mapping[str, str] | None = None,
        resume: bool = True,
        resume_key: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> StageResult:
        if not NAME_RE.fullmatch(product):
            raise StageError(f"invalid product name: {product!r}")
        if not NAME_RE.fullmatch(stage):
            raise StageError(f"invalid stage name: {stage!r}")
        argv = [str(value) for value in command]
        if not argv or not argv[0]:
            raise StageError("stage command must be a non-empty argv sequence")
        outputs = [_relative_output(value).as_posix() for value in expected_outputs]
        env_overlay = {str(key): str(value) for key, value in (environment or {}).items()}

        identifier = build_id or self.create_build(product, metadata)
        build = self.history.get_build(identifier)
        if build is None:
            raise StageError(f"unknown build id: {identifier}")
        if build["product"] != product:
            raise StageError(
                f"build {identifier} belongs to {build['product']!r}, not {product!r}"
            )
        stage_root = self.builds_root / identifier / stage
        stage_root.mkdir(parents=True, exist_ok=True)
        key = resume_key or _resume_key(argv, env_overlay, outputs)

        reusable = self.history.reusable_attempt(identifier, stage, key) if resume and outputs else None
        if reusable is not None:
            saved = json.loads(reusable["checkpoint_json"])
            try:
                current = snapshot_outputs(stage_root, outputs)
            except StageError:
                current = None
            if current == saved:
                attempt_no = len(
                    [
                        item
                        for item in self.history.attempts(identifier)
                        if item["stage_name"] == stage
                    ]
                ) + 1
                stdout_log = stage_root / f"stdout.attempt-{attempt_no}.log"
                stderr_log = stage_root / f"stderr.attempt-{attempt_no}.log"
                stdout_log.write_text("checkpoint reused\n", encoding="utf-8")
                stderr_log.write_bytes(b"")
                reused_attempt_id = int(reusable["attempt_id"])
                attempt_id = self.history.record_skip(
                    build_id=identifier,
                    stage_name=stage,
                    command=argv,
                    cwd=stage_root,
                    stdout_log=stdout_log,
                    stderr_log=stderr_log,
                    resume_key=key,
                    reused_attempt_id=reused_attempt_id,
                    checkpoint=saved,
                )
                return StageResult(
                    identifier,
                    attempt_id,
                    product,
                    stage,
                    "skipped",
                    0,
                    0.0,
                    str(stdout_log),
                    str(stderr_log),
                    saved,
                    reused_attempt_id,
                )

        attempt_no = len(
            [
                item
                for item in self.history.attempts(identifier)
                if item["stage_name"] == stage
            ]
        ) + 1
        stdout_log = stage_root / f"stdout.attempt-{attempt_no}.log"
        stderr_log = stage_root / f"stderr.attempt-{attempt_no}.log"
        started = time.monotonic()
        attempt_id = self.history.begin_attempt(
            build_id=identifier,
            stage_name=stage,
            command=argv,
            cwd=stage_root,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            resume_key=key,
        )
        env = os.environ.copy()
        env.update(env_overlay)
        live = stage in LIVE_OUTPUT_STAGES
        threads: list[threading.Thread] = []

        try:
            with stdout_log.open("wb") as stdout_handle, stderr_log.open("wb") as stderr_handle:
                process = subprocess.Popen(
                    argv,
                    cwd=stage_root,
                    stdout=subprocess.PIPE if live else stdout_handle,
                    stderr=subprocess.PIPE if live else stderr_handle,
                    env=env,
                    start_new_session=True,
                )
                self.history.update_attempt_pid(attempt_id, process.pid)
                if live:
                    assert process.stdout is not None and process.stderr is not None
                    for pipe, log_handle in (
                        (process.stdout, stdout_handle),
                        (process.stderr, stderr_handle),
                    ):
                        thread = threading.Thread(
                            target=_tee_live_output,
                            args=(pipe, log_handle, stage),
                            daemon=True,
                        )
                        thread.start()
                        threads.append(thread)
                try:
                    raw_status, usage = _wait_with_heartbeat(process, stage, started)
                except KeyboardInterrupt:
                    _terminate_group(process)
                    process.wait()
                    for thread in threads:
                        thread.join(timeout=2.0)
                    duration = time.monotonic() - started
                    self.history.finish_attempt(
                        attempt_id,
                        status="interrupted",
                        duration_seconds=duration,
                        exit_code=130,
                        error="interrupted by user",
                    )
                    raise
                finally:
                    for thread in threads:
                        thread.join(timeout=2.0)
        except KeyboardInterrupt:
            raise
        except OSError as exc:
            duration = time.monotonic() - started
            self.history.finish_attempt(
                attempt_id,
                status="failed",
                duration_seconds=duration,
                exit_code=1,
                error=str(exc),
            )
            raise StageError(f"cannot run stage {stage!r}: {exc}") from exc

        exit_code = os.waitstatus_to_exitcode(raw_status)
        duration = time.monotonic() - started
        checkpoint = None
        error: str | None = None
        status = "success" if exit_code == 0 else "failed"
        if status == "success" and outputs:
            try:
                checkpoint = snapshot_outputs(stage_root, outputs)
            except StageError as exc:
                status = "failed"
                exit_code = 1
                error = str(exc)

        self.history.finish_attempt(
            attempt_id,
            status=status,
            duration_seconds=duration,
            exit_code=exit_code,
            metrics=_usage_metrics(usage),
            checkpoint=checkpoint,
            error=error,
        )
        return StageResult(
            identifier,
            attempt_id,
            product,
            stage,
            status,
            exit_code,
            duration,
            str(stdout_log),
            str(stderr_log),
            checkpoint,
        )
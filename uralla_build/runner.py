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
import time
from typing import Mapping, Sequence

from .errors import StageError
from .history import HistoryStore


NAME_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


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
    }


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


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
                stdout_log.write_text(
                    f"checkpoint reused from attempt {reusable['attempt_id']}\n",
                    encoding="utf-8",
                )
                stderr_log.touch()
                attempt_id = self.history.record_skip(
                    build_id=identifier,
                    stage_name=stage,
                    command=argv,
                    cwd=stage_root,
                    stdout_log=stdout_log,
                    stderr_log=stderr_log,
                    resume_key=key,
                    reused_attempt_id=int(reusable["attempt_id"]),
                    checkpoint=current,
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
                    current,
                    int(reusable["attempt_id"]),
                )

        attempt_no = len(
            [item for item in self.history.attempts(identifier) if item["stage_name"] == stage]
        ) + 1
        stdout_log = stage_root / f"stdout.attempt-{attempt_no}.log"
        stderr_log = stage_root / f"stderr.attempt-{attempt_no}.log"
        attempt_id = self.history.begin_attempt(
            build_id=identifier,
            stage_name=stage,
            command=argv,
            cwd=stage_root,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            resume_key=key,
        )
        started = time.monotonic()
        process: subprocess.Popen[bytes] | None = None
        metrics: dict[str, int | float] = {}
        exit_code: int | None = None
        terminal_status = "failed"
        checkpoint: list[dict[str, object]] | None = None
        error: str | None = None
        try:
            with stdout_log.open("wb") as stdout, stderr_log.open("wb") as stderr:
                process = subprocess.Popen(
                    argv,
                    cwd=stage_root,
                    env={**os.environ, **env_overlay},
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=True,
                )
                self.history.update_attempt_pid(attempt_id, process.pid)
                _, status, usage = os.wait4(process.pid, 0)
                exit_code = os.waitstatus_to_exitcode(status)
                process.returncode = exit_code
                metrics = _usage_metrics(usage)
            if exit_code != 0:
                error = f"command exited with code {exit_code}"
            else:
                checkpoint = snapshot_outputs(stage_root, outputs)
                terminal_status = "success"
        except KeyboardInterrupt:
            terminal_status = "interrupted"
            error = "stage interrupted"
            if process is not None:
                _terminate_group(process)
                try:
                    _, status, usage = os.wait4(process.pid, 0)
                    exit_code = os.waitstatus_to_exitcode(status)
                    process.returncode = exit_code
                    metrics = _usage_metrics(usage)
                except ChildProcessError:
                    exit_code = process.returncode
        except (OSError, StageError) as exc:
            error = str(exc)
        duration = time.monotonic() - started
        self.history.finish_attempt(
            attempt_id,
            status=terminal_status,
            duration_seconds=duration,
            exit_code=exit_code,
            metrics=metrics,
            checkpoint=checkpoint,
            error=error,
        )
        result_exit_code = exit_code if exit_code not in {None, 0} else (
            0 if terminal_status == "success" else 1
        )
        result = StageResult(
            identifier,
            attempt_id,
            product,
            stage,
            terminal_status,
            result_exit_code,
            duration,
            str(stdout_log),
            str(stderr_log),
            checkpoint,
        )
        if terminal_status == "interrupted":
            raise KeyboardInterrupt
        return result

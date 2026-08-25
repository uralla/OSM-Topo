"""Persistent SQLite history for build and stage execution."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Mapping
from uuid import uuid4

from .errors import StageError


SCHEMA = """
CREATE TABLE IF NOT EXISTS builds (
    build_id TEXT PRIMARY KEY,
    product TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'interrupted')),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stage_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id TEXT NOT NULL REFERENCES builds(build_id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    attempt_no INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'interrupted', 'skipped')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_seconds REAL,
    exit_code INTEGER,
    command_json TEXT NOT NULL,
    cwd TEXT NOT NULL,
    pid INTEGER,
    stdout_log TEXT NOT NULL,
    stderr_log TEXT NOT NULL,
    cpu_user_seconds REAL,
    cpu_system_seconds REAL,
    peak_rss_kib INTEGER,
    minor_faults INTEGER,
    major_faults INTEGER,
    resume_key TEXT NOT NULL,
    checkpoint_json TEXT,
    error TEXT,
    reused_attempt_id INTEGER REFERENCES stage_attempts(attempt_id),
    UNIQUE (build_id, stage_name, attempt_no)
);

CREATE INDEX IF NOT EXISTS stage_attempts_lookup
    ON stage_attempts(build_id, stage_name, status, attempt_no DESC);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class HistoryStore:
    """Small transactional API around the on-disk build history."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute("PRAGMA user_version = 1")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_build(
        self,
        product: str,
        metadata: Mapping[str, Any] | None = None,
        build_id: str | None = None,
    ) -> str:
        identifier = build_id or uuid4().hex
        with self.connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO builds VALUES (?, ?, 'running', ?, NULL, ?)",
                    (identifier, product, utc_now(), json.dumps(metadata or {}, sort_keys=True)),
                )
            except sqlite3.IntegrityError as exc:
                raise StageError(f"build id already exists: {identifier}") from exc
        return identifier

    def get_build(self, build_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM builds WHERE build_id = ?", (build_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def set_build_status(self, build_id: str, status: str) -> None:
        if status not in {"running", "success", "failed", "interrupted"}:
            raise StageError(f"invalid build status: {status}")
        finished_at = None if status == "running" else utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE builds SET status = ?, finished_at = ? WHERE build_id = ?",
                (status, finished_at, build_id),
            )
            if cursor.rowcount != 1:
                raise StageError(f"unknown build id: {build_id}")

    def begin_attempt(
        self,
        *,
        build_id: str,
        stage_name: str,
        command: list[str],
        cwd: Path,
        stdout_log: Path,
        stderr_log: Path,
        resume_key: str,
        pid: int | None = None,
        status: str = "running",
        reused_attempt_id: int | None = None,
    ) -> int:
        with self.connect() as connection:
            build = connection.execute(
                "SELECT status FROM builds WHERE build_id = ?", (build_id,)
            ).fetchone()
            if build is None:
                raise StageError(f"unknown build id: {build_id}")
            if build["status"] != "running":
                raise StageError(f"build {build_id} is {build['status']}, not running")
            if status == "running":
                active = connection.execute(
                    """SELECT attempt_id FROM stage_attempts
                       WHERE build_id = ? AND stage_name = ? AND status = 'running'""",
                    (build_id, stage_name),
                ).fetchone()
                if active is not None:
                    raise StageError(
                        f"stage {stage_name!r} already has running attempt {active['attempt_id']}"
                    )
            attempt_no = connection.execute(
                """SELECT COALESCE(MAX(attempt_no), 0) + 1
                   FROM stage_attempts WHERE build_id = ? AND stage_name = ?""",
                (build_id, stage_name),
            ).fetchone()[0]
            cursor = connection.execute(
                """INSERT INTO stage_attempts (
                       build_id, stage_name, attempt_no, status, started_at,
                       command_json, cwd, pid, stdout_log, stderr_log,
                       resume_key, reused_attempt_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    build_id,
                    stage_name,
                    attempt_no,
                    status,
                    utc_now(),
                    json.dumps(command, ensure_ascii=False),
                    str(cwd),
                    pid,
                    str(stdout_log),
                    str(stderr_log),
                    resume_key,
                    reused_attempt_id,
                ),
            )
            return int(cursor.lastrowid)

    def update_attempt_pid(self, attempt_id: int, pid: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE stage_attempts SET pid = ? WHERE attempt_id = ?", (pid, attempt_id)
            )

    def finish_attempt(
        self,
        attempt_id: int,
        *,
        status: str,
        duration_seconds: float,
        exit_code: int | None,
        metrics: Mapping[str, int | float] | None = None,
        checkpoint: object | None = None,
        error: str | None = None,
    ) -> None:
        if status not in {"success", "failed", "interrupted", "skipped"}:
            raise StageError(f"invalid terminal stage status: {status}")
        values = metrics or {}
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE stage_attempts SET
                       status = ?, finished_at = ?, duration_seconds = ?, exit_code = ?,
                       cpu_user_seconds = ?, cpu_system_seconds = ?, peak_rss_kib = ?,
                       minor_faults = ?, major_faults = ?, checkpoint_json = ?, error = ?
                   WHERE attempt_id = ? AND status = 'running'""",
                (
                    status,
                    utc_now(),
                    duration_seconds,
                    exit_code,
                    values.get("cpu_user_seconds"),
                    values.get("cpu_system_seconds"),
                    values.get("peak_rss_kib"),
                    values.get("minor_faults"),
                    values.get("major_faults"),
                    json.dumps(checkpoint, sort_keys=True) if checkpoint is not None else None,
                    error,
                    attempt_id,
                ),
            )
            if cursor.rowcount != 1:
                raise StageError(f"attempt {attempt_id} is missing or already terminal")

    def record_skip(
        self,
        *,
        build_id: str,
        stage_name: str,
        command: list[str],
        cwd: Path,
        stdout_log: Path,
        stderr_log: Path,
        resume_key: str,
        reused_attempt_id: int,
        checkpoint: object,
    ) -> int:
        attempt_id = self.begin_attempt(
            build_id=build_id,
            stage_name=stage_name,
            command=command,
            cwd=cwd,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            resume_key=resume_key,
            status="running",
            reused_attempt_id=reused_attempt_id,
        )
        self.finish_attempt(
            attempt_id,
            status="skipped",
            duration_seconds=0.0,
            exit_code=0,
            checkpoint=checkpoint,
        )
        return attempt_id

    def reusable_attempt(
        self, build_id: str, stage_name: str, resume_key: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM stage_attempts
                   WHERE build_id = ? AND stage_name = ? AND status = 'success'
                     AND resume_key = ? AND checkpoint_json IS NOT NULL
                   ORDER BY attempt_no DESC LIMIT 1""",
                (build_id, stage_name, resume_key),
            ).fetchone()
        return dict(row) if row is not None else None

    def attempts(self, build_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM stage_attempts WHERE build_id = ?
                   ORDER BY attempt_id""",
                (build_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_success_by_product(self) -> dict[str, str]:
        """Return the latest successful build completion for each product."""

        with self.connect() as connection:
            rows = connection.execute(
                """SELECT product, MAX(finished_at) AS finished_at
                   FROM builds
                   WHERE status = 'success' AND finished_at IS NOT NULL
                   GROUP BY product"""
            ).fetchall()
        return {str(row["product"]): str(row["finished_at"]) for row in rows}

    def running_products(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT product FROM builds WHERE status = 'running'"
            ).fetchall()
        return {str(row["product"]) for row in rows}

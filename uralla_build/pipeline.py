"""Product pipeline with parallel light phases and an exclusive heavy tail."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import errno
import fcntl
import hashlib
from pathlib import Path
from pathlib import PurePosixPath
from typing import Callable, Iterator, Mapping, Sequence

from .errors import StageError
from .runner import StageResult, StageRunner


@dataclass(frozen=True, slots=True)
class PipelineStage:
    name: str
    command: tuple[str, ...]
    expected_outputs: tuple[str, ...] = ()
    prepare_directories: tuple[str, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    resume_key: str | None = None
    exclusive_host: bool = False


@dataclass(frozen=True, slots=True)
class PipelineResult:
    build_id: str
    product: str
    status: str
    stages: tuple[StageResult, ...]
    final_result: object | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "build_id": self.build_id,
            "product": self.product,
            "status": self.status,
            "stages": [asdict(stage) for stage in self.stages],
            "final_result": self.final_result,
        }


@contextmanager
def exclusive_product_lock(work_root: Path, product: str) -> Iterator[None]:
    """Prevent two pipelines for the same product while allowing other products."""

    state = work_root / "state" / "product-locks"
    state.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(product.encode("utf-8")).hexdigest()[:24]
    path = state / f"{digest}.lock"
    handle = path.open("a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise StageError(f"another pipeline for {product!r} holds {path}") from exc
            raise
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


class _PipelineResourceLease:
    """Shared for extract/preprocess/merge, upgraded to exclusive before splitter.

    A separate turnstile lock prevents fresh shared users from entering once a
    product is waiting to upgrade.  This gives splitter/mkgmap the whole host
    after already-running light phases reach their boundary.
    """

    def __init__(self, work_root: Path):
        state = work_root / "state"
        state.mkdir(parents=True, exist_ok=True)
        self.resource_path = state / "pipeline.lock"
        self.gate_path = state / "pipeline-gate.lock"
        self.resource = self.resource_path.open("a+b")
        self.gate = self.gate_path.open("a+b")
        self.exclusive = False
        self.entered = False

    def __enter__(self) -> "_PipelineResourceLease":
        fcntl.flock(self.gate.fileno(), fcntl.LOCK_SH)
        try:
            fcntl.flock(self.resource.fileno(), fcntl.LOCK_SH)
        finally:
            fcntl.flock(self.gate.fileno(), fcntl.LOCK_UN)
        self.entered = True
        return self

    def upgrade(self) -> None:
        if self.exclusive:
            return
        if not self.entered:
            raise RuntimeError("pipeline resource lease was not entered")

        # Close the entrance for new light phases before releasing our shared
        # resource lock. Existing light phases may finish, then we take the host.
        fcntl.flock(self.gate.fileno(), fcntl.LOCK_EX)
        try:
            fcntl.flock(self.resource.fileno(), fcntl.LOCK_UN)
            fcntl.flock(self.resource.fileno(), fcntl.LOCK_EX)
            self.exclusive = True
        finally:
            fcntl.flock(self.gate.fileno(), fcntl.LOCK_UN)

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        try:
            if self.entered:
                fcntl.flock(self.resource.fileno(), fcntl.LOCK_UN)
        finally:
            self.resource.close()
            self.gate.close()


class PipelineRunner:
    """Run explicit stages in order and own the terminal build status."""

    def __init__(self, runner: StageRunner):
        self.runner = runner

    def run(
        self,
        *,
        product: str,
        stages: Sequence[PipelineStage] | Callable[[str], Sequence[PipelineStage]],
        build_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        resume: bool = True,
        finalize: Callable[[str], object] | None = None,
    ) -> PipelineResult:
        if not callable(stages) and not stages:
            raise StageError("product pipeline must contain at least one stage")

        with exclusive_product_lock(self.runner.work_root, product):
            with _PipelineResourceLease(self.runner.work_root) as resources:
                identifier = build_id or self.runner.create_build(product, metadata)
                build = self.runner.history.get_build(identifier)
                if build is None:
                    raise StageError(f"unknown build id: {identifier}")
                if build["product"] != product:
                    raise StageError(
                        f"build {identifier} belongs to {build['product']!r}, not {product!r}"
                    )
                if build["status"] != "running":
                    raise StageError(
                        f"build {identifier} is {build['status']}, not running"
                    )

                resolved_stages = tuple(stages(identifier) if callable(stages) else stages)
                if not resolved_stages:
                    self.runner.history.set_build_status(identifier, "failed")
                    raise StageError("product pipeline must contain at least one stage")
                results: list[StageResult] = []
                try:
                    for stage in resolved_stages:
                        if stage.exclusive_host:
                            resources.upgrade()
                        stage_root = self.runner.builds_root / identifier / stage.name
                        for raw_directory in stage.prepare_directories:
                            relative = PurePosixPath(raw_directory)
                            if (
                                not raw_directory
                                or relative.is_absolute()
                                or ".." in relative.parts
                                or relative == PurePosixPath(".")
                            ):
                                raise StageError(
                                    "prepared directory must be a safe relative path: "
                                    f"{raw_directory!r}"
                                )
                            stage_root.joinpath(*relative.parts).mkdir(
                                parents=True, exist_ok=True
                            )
                        result = self.runner.run(
                            product=product,
                            stage=stage.name,
                            command=stage.command,
                            build_id=identifier,
                            expected_outputs=stage.expected_outputs,
                            environment=dict(stage.environment),
                            resume=resume,
                            resume_key=stage.resume_key,
                        )
                        results.append(result)
                        if result.status not in {"success", "skipped"}:
                            self.runner.history.set_build_status(identifier, "failed")
                            return PipelineResult(
                                identifier, product, "failed", tuple(results)
                            )
                    final_result = finalize(identifier) if finalize is not None else None
                except KeyboardInterrupt:
                    self.runner.history.set_build_status(identifier, "interrupted")
                    raise
                except Exception:
                    self.runner.history.set_build_status(identifier, "failed")
                    raise

                self.runner.history.set_build_status(identifier, "success")
                return PipelineResult(
                    identifier, product, "success", tuple(results), final_result
                )

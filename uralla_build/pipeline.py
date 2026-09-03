"""Sequential product pipeline with one global build lock."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import errno
import fcntl
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
def exclusive_pipeline_lock(work_root: Path) -> Iterator[None]:
    """Prevent concurrent product pipelines on the configured build host."""

    state = work_root / "state"
    state.mkdir(parents=True, exist_ok=True)
    path = state / "pipeline.lock"
    handle = path.open("a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise StageError(f"another product pipeline holds {path}") from exc
            raise
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


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
        status_changed: Callable[[str, str], None] | None = None,
    ) -> PipelineResult:
        if not callable(stages) and not stages:
            raise StageError("product pipeline must contain at least one stage")

        def notify(status: str) -> None:
            if status_changed is not None:
                status_changed(product, status)

        with exclusive_pipeline_lock(self.runner.work_root):
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
            notify("running")

            resolved_stages = tuple(stages(identifier) if callable(stages) else stages)
            if not resolved_stages:
                self.runner.history.set_build_status(identifier, "failed")
                notify("failed")
                raise StageError("product pipeline must contain at least one stage")
            results: list[StageResult] = []
            try:
                for stage in resolved_stages:
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
                        notify("failed")
                        return PipelineResult(
                            identifier, product, "failed", tuple(results)
                        )
                final_result = finalize(identifier) if finalize is not None else None
            except KeyboardInterrupt:
                self.runner.history.set_build_status(identifier, "interrupted")
                notify("interrupted")
                raise
            except Exception:
                self.runner.history.set_build_status(identifier, "failed")
                notify("failed")
                raise

            self.runner.history.set_build_status(identifier, "success")
            notify("success")
            return PipelineResult(
                identifier, product, "success", tuple(results), final_result
            )
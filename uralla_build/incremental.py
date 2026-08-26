"""Fast rebuild paths that reuse validated outputs from a previous successful build."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Mapping

from .bootstrap import load_tools_lock
from .build_plan import ProductBuildPlan, plan_product_build
from .errors import StageError
from .history import HistoryStore
from .host import HostConfig
from .pipeline import PipelineRunner, PipelineStage
from .publish import publish_product
from .runner import StageRunner


def _latest_successful_build(history: HistoryStore, product: str) -> str:
    with history.connect() as connection:
        row = connection.execute(
            """SELECT build_id FROM builds
               WHERE product = ? AND status = 'success'
               ORDER BY finished_at DESC LIMIT 1""",
            (product,),
        ).fetchone()
    if row is None:
        raise StageError(
            f"no successful build exists for {product!r}; run one full build first"
        )
    return str(row["build_id"])


def rebuild_from_mkgmap(
    manifest: Mapping[str, object],
    host: HostConfig,
    *,
    product_key: str,
    repo_root: str | Path,
    manifest_path: str | Path,
    tools_lock_path: str | Path,
    build_id: str | None = None,
) -> dict[str, object]:
    """Run only mkgmap and publication using splitter output from latest success."""

    products = manifest.get("products")
    product = products.get(product_key) if isinstance(products, Mapping) else None
    if not isinstance(product, Mapping):
        raise StageError(f"unknown product: {product_key}")

    runner = StageRunner(host.paths.work_root)
    previous_id = _latest_successful_build(runner.history, product_key)
    previous_tiles = runner.builds_root / previous_id / "splitter" / "tiles"
    previous_template = previous_tiles / "template.args"
    previous_areas = previous_tiles / "areas.list"
    if not previous_template.is_file():
        raise StageError(
            f"latest successful build {previous_id} has no splitter template: {previous_template}"
        )
    if not previous_areas.is_file():
        raise StageError(
            f"latest successful build {previous_id} has no splitter areas: {previous_areas}"
        )

    metadata = {
        "mode": "from-stage:mkgmap",
        "reused_build_id": previous_id,
        "reused_splitter": str(previous_tiles),
    }
    if build_id is None:
        identifier = runner.create_build(product_key, metadata)
    else:
        identifier = runner.history.create_build(
            product_key,
            metadata,
            build_id=build_id,
        )

    build = runner.history.get_build(identifier)
    if build is None:
        raise StageError(f"unknown build id after creation: {identifier}")
    created = date.fromisoformat(str(build["created_at"])[:10])

    lock = load_tools_lock(tools_lock_path)
    plan: ProductBuildPlan = plan_product_build(
        manifest,
        host,
        lock,
        product_key=product_key,
        build_id=identifier,
        repo_root=repo_root,
        manifest_path=manifest_path,
        build_date=created,
    )
    current_mkgmap = next((stage for stage in plan.stages if stage.name == "mkgmap"), None)
    if current_mkgmap is None:
        runner.history.set_build_status(identifier, "failed")
        raise StageError("build plan contains no mkgmap stage")

    current_template = runner.builds_root / identifier / "splitter" / "tiles" / "template.args"
    command = tuple(
        str(previous_template) if argument == str(current_template) else argument
        for argument in current_mkgmap.command
    )
    if command == current_mkgmap.command:
        runner.history.set_build_status(identifier, "failed")
        raise StageError("could not substitute previous splitter template into mkgmap command")

    mkgmap_stage = PipelineStage(
        current_mkgmap.name,
        command,
        current_mkgmap.expected_outputs,
        current_mkgmap.prepare_directories,
        current_mkgmap.environment,
        current_mkgmap.resume_key,
    )

    def finalize(_build_id: str) -> object:
        artifacts = publish_product(
            host,
            product,
            plan.img_source,
            plan.gmapi_source,
        )
        return [artifact.to_dict() for artifact in artifacts]

    pipeline = PipelineRunner(runner)
    result = pipeline.run(
        product=product_key,
        stages=(mkgmap_stage,),
        build_id=identifier,
        metadata=None,
        resume=False,
        finalize=finalize,
    )
    return {
        "mode": "apply",
        "from_stage": "mkgmap",
        "reused_build_id": previous_id,
        "reused_splitter": str(previous_tiles),
        "result": result.to_dict(),
    }

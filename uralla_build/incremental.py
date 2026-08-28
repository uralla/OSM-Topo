"""Fast rebuild paths that reuse existing splitter outputs."""

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


def _latest_reusable_splitter_build(
    history: HistoryStore,
    builds_root: Path,
    product: str,
) -> tuple[str, Path]:
    with history.connect() as connection:
        rows = connection.execute(
            """SELECT build_id FROM builds
               WHERE product = ?
               ORDER BY COALESCE(finished_at, created_at) DESC""",
            (product,),
        ).fetchall()

    for row in rows:
        build_id = str(row["build_id"])
        tiles = builds_root / build_id / "splitter" / "tiles"
        if (tiles / "template.args").is_file() and (tiles / "areas.list").is_file():
            return build_id, tiles

    raise StageError(
        f"no build with reusable splitter output exists for {product!r}; "
        "run one full build first"
    )


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
    """Run only mkgmap and publication using latest reusable splitter output."""

    products = manifest.get("products")
    product = products.get(product_key) if isinstance(products, Mapping) else None
    if not isinstance(product, Mapping):
        raise StageError(f"unknown product: {product_key}")

    runner = StageRunner(host.paths.work_root)
    previous_id, previous_tiles = _latest_reusable_splitter_build(
        runner.history,
        runner.builds_root,
        product_key,
    )
    previous_template = previous_tiles / "template.args"

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

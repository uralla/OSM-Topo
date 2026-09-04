import json
import sys
from datetime import datetime, timezone

from uralla_build.history import HistoryStore
from uralla_build.map_recipe import map_recipe_fingerprint
from uralla_build.pipeline import PipelineRunner, PipelineStage
from uralla_build.public_status import build_public_status_snapshot
from uralla_build.runner import StageRunner


def _manifest():
    return {
        "defaults": {"enabled": True, "priority": 100, "update_interval_days": 7},
        "sources": {"src": {"path": "input/source.osm.pbf"}},
        "products": {
            "demo": {
                "source": "src",
                "names": {"family": "Demo", "output_img": "Demo.img"},
                "web": {"title": "Демо", "order": 1, "visible": True},
                "splitter": {"max_nodes": 1000},
            }
        },
    }


def _success(history, recipe):
    metadata = {} if recipe is None else {"map_recipe": recipe}
    with history.connect() as connection:
        connection.execute(
            "INSERT INTO builds(build_id, product, status, created_at, finished_at, metadata_json) "
            "VALUES (?, 'demo', 'success', ?, ?, ?)",
            (
                "success-" + (recipe or "legacy")[:12],
                "2026-09-04T08:00:00+00:00",
                "2026-09-04T09:00:00+00:00",
                json.dumps(metadata),
            ),
        )


def test_recipe_ignores_web_only_changes():
    manifest = _manifest()
    original = map_recipe_fingerprint(manifest, "demo")
    manifest["products"]["demo"]["web"]["title"] = "Новое публичное название"
    assert map_recipe_fingerprint(manifest, "demo") == original


def test_recipe_changes_for_map_configuration():
    manifest = _manifest()
    original = map_recipe_fingerprint(manifest, "demo")
    manifest["products"]["demo"]["splitter"]["max_nodes"] = 2000
    assert map_recipe_fingerprint(manifest, "demo") != original


def test_public_status_reports_current_stale_and_legacy(tmp_path):
    manifest = _manifest()
    current = map_recipe_fingerprint(manifest, "demo")

    current_history = HistoryStore(tmp_path / "current.sqlite3")
    _success(current_history, current)
    snapshot = build_public_status_snapshot(
        manifest,
        current_history,
        now=datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert snapshot["products"][0]["recipe_state"] == "current"

    stale_history = HistoryStore(tmp_path / "stale.sqlite3")
    _success(stale_history, "0" * 64)
    snapshot = build_public_status_snapshot(
        manifest,
        stale_history,
        now=datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert snapshot["products"][0]["recipe_state"] == "stale"

    legacy_history = HistoryStore(tmp_path / "legacy.sqlite3")
    _success(legacy_history, None)
    snapshot = build_public_status_snapshot(
        manifest,
        legacy_history,
        now=datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert snapshot["products"][0]["recipe_state"] == "legacy"


def test_pipeline_records_recipe_in_build_metadata(tmp_path):
    manifest_path = tmp_path / "repo" / "config" / "maps.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        "defaults: {}\n"
        "sources:\n  src:\n    path: input/source.osm.pbf\n"
        "products:\n  demo:\n    source: src\n    names:\n      output_img: Demo.img\n",
        encoding="utf-8",
    )
    runner = StageRunner(tmp_path / "work")
    pipeline = PipelineRunner(runner)
    result = pipeline.run(
        product="demo",
        stages=(
            PipelineStage(
                "make",
                (sys.executable, "-c", "from pathlib import Path; Path('ok').write_text('ok')"),
                ("ok",),
            ),
        ),
        metadata={"manifest": str(manifest_path)},
    )
    build = runner.history.get_build(result.build_id)
    metadata = json.loads(build["metadata_json"])
    assert metadata["map_recipe"] == map_recipe_fingerprint(
        json.loads(json.dumps({
            "defaults": {},
            "sources": {"src": {"path": "input/source.osm.pbf"}},
            "products": {"demo": {"source": "src", "names": {"output_img": "Demo.img"}}},
        })),
        "demo",
        repo_root=manifest_path.parent.parent,
    )

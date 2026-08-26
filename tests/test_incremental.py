from __future__ import annotations

from pathlib import Path

import pytest

from uralla_build.errors import StageError
from uralla_build.history import HistoryStore
from uralla_build.incremental import _latest_successful_splitter_build


def _set_terminal_build(
    history: HistoryStore,
    build_id: str,
    *,
    status: str,
    finished_at: str,
) -> None:
    with history.connect() as connection:
        connection.execute(
            "UPDATE builds SET status = ?, finished_at = ? WHERE build_id = ?",
            (status, finished_at, build_id),
        )


def _make_splitter_checkpoint(builds_root: Path, build_id: str) -> Path:
    tiles = builds_root / build_id / "splitter" / "tiles"
    tiles.mkdir(parents=True)
    (tiles / "template.args").write_text("63240001.osm.pbf\n", encoding="utf-8")
    (tiles / "areas.list").write_text("63240001: test area\n", encoding="utf-8")
    return tiles


def test_latest_successful_splitter_build_skips_newer_fast_success(tmp_path: Path) -> None:
    """A later mkgmap-only SUCCESS must not hide the last reusable full build."""

    history = HistoryStore(tmp_path / "state" / "history.sqlite3")
    builds_root = tmp_path / "builds"

    history.create_build("crimea", build_id="full-success")
    reusable_tiles = _make_splitter_checkpoint(builds_root, "full-success")
    _set_terminal_build(
        history,
        "full-success",
        status="success",
        finished_at="2026-08-26T10:00:00+00:00",
    )

    # This represents a newer --from-stage mkgmap build. It is successful but has
    # no splitter directory of its own, so it must be skipped during reuse lookup.
    history.create_build("crimea", build_id="fast-success")
    _set_terminal_build(
        history,
        "fast-success",
        status="success",
        finished_at="2026-08-26T11:00:00+00:00",
    )

    # Even a newer reusable build for another product must not be considered.
    history.create_build("ural", build_id="other-product")
    _make_splitter_checkpoint(builds_root, "other-product")
    _set_terminal_build(
        history,
        "other-product",
        status="success",
        finished_at="2026-08-26T12:00:00+00:00",
    )

    build_id, tiles = _latest_successful_splitter_build(
        history,
        builds_root,
        "crimea",
    )

    assert build_id == "full-success"
    assert tiles == reusable_tiles


def test_latest_successful_splitter_build_requires_real_checkpoint(tmp_path: Path) -> None:
    history = HistoryStore(tmp_path / "state" / "history.sqlite3")
    builds_root = tmp_path / "builds"

    history.create_build("crimea", build_id="success-without-splitter")
    _set_terminal_build(
        history,
        "success-without-splitter",
        status="success",
        finished_at="2026-08-26T11:00:00+00:00",
    )

    with pytest.raises(StageError, match="no successful build with reusable splitter output"):
        _latest_successful_splitter_build(history, builds_root, "crimea")

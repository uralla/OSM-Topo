from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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


class IncrementalBuildTests(unittest.TestCase):
    def test_latest_successful_splitter_build_skips_newer_fast_success(self) -> None:
        """A later mkgmap-only SUCCESS must not hide the last reusable full build."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            history = HistoryStore(root / "state" / "history.sqlite3")
            builds_root = root / "builds"

            history.create_build("crimea", build_id="full-success")
            reusable_tiles = _make_splitter_checkpoint(builds_root, "full-success")
            _set_terminal_build(
                history,
                "full-success",
                status="success",
                finished_at="2026-08-26T10:00:00+00:00",
            )

            # A newer --from-stage mkgmap build can be successful without a
            # splitter directory, so it must not hide the reusable full build.
            history.create_build("crimea", build_id="fast-success")
            _set_terminal_build(
                history,
                "fast-success",
                status="success",
                finished_at="2026-08-26T11:00:00+00:00",
            )

            # A reusable build for another product must also be ignored.
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

            self.assertEqual(build_id, "full-success")
            self.assertEqual(tiles, reusable_tiles)

    def test_latest_successful_splitter_build_requires_real_checkpoint(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            history = HistoryStore(root / "state" / "history.sqlite3")
            builds_root = root / "builds"

            history.create_build("crimea", build_id="success-without-splitter")
            _set_terminal_build(
                history,
                "success-without-splitter",
                status="success",
                finished_at="2026-08-26T11:00:00+00:00",
            )

            with self.assertRaisesRegex(
                StageError,
                "no successful build with reusable splitter output",
            ):
                _latest_successful_splitter_build(history, builds_root, "crimea")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.history import HistoryStore
from uralla_build.runner import StageRunner


def _write_command(filename: str = "result.txt", content: str = "ok") -> list[str]:
    code = (
        "from pathlib import Path; "
        f"Path({filename!r}).write_text({content!r}, encoding='utf-8')"
    )
    return [sys.executable, "-c", code]


class StageRunnerTests(unittest.TestCase):
    def test_v1_history_is_migrated_with_io_metrics(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "history.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TABLE stage_attempts (
                        attempt_id INTEGER PRIMARY KEY,
                        build_id TEXT NOT NULL,
                        stage_name TEXT NOT NULL,
                        attempt_no INTEGER NOT NULL,
                        status TEXT NOT NULL
                    );
                    PRAGMA user_version = 1;
                    """
                )

            HistoryStore(database)

            with sqlite3.connect(database) as connection:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(stage_attempts)")
                }
                version = connection.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, 2)
            self.assertTrue(
                {"swaps", "block_input_operations", "block_output_operations"}
                <= columns
            )

    def test_success_is_checkpointed_with_metrics_and_logs(self) -> None:
        with TemporaryDirectory() as directory:
            runner = StageRunner(Path(directory) / "work")
            result = runner.run(
                product="armenia",
                stage="splitter",
                command=_write_command(),
                expected_outputs=["result.txt"],
            )
            self.assertEqual(result.status, "success")
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(Path(result.stdout_log).is_file())
            attempts = runner.history.attempts(result.build_id)
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["status"], "success")
            self.assertIsNotNone(attempts[0]["peak_rss_kib"])
            self.assertIsNotNone(attempts[0]["swaps"])
            self.assertIsNotNone(attempts[0]["block_input_operations"])
            self.assertIsNotNone(attempts[0]["block_output_operations"])
            checkpoint = json.loads(attempts[0]["checkpoint_json"])
            self.assertEqual(checkpoint[0]["path"], "result.txt")
            self.assertGreater(checkpoint[0]["size"], 0)

    def test_matching_checkpoint_is_reused_within_same_build(self) -> None:
        with TemporaryDirectory() as directory:
            runner = StageRunner(Path(directory) / "work")
            first = runner.run(
                product="armenia",
                stage="splitter",
                command=_write_command(),
                expected_outputs=["result.txt"],
            )
            second = runner.run(
                product="armenia",
                stage="splitter",
                command=_write_command(),
                build_id=first.build_id,
                expected_outputs=["result.txt"],
            )
            self.assertEqual(second.status, "skipped")
            self.assertEqual(second.reused_attempt_id, first.attempt_id)
            attempts = runner.history.attempts(first.build_id)
            self.assertEqual([item["status"] for item in attempts], ["success", "skipped"])
            self.assertIn("checkpoint reused", Path(second.stdout_log).read_text(encoding="utf-8"))

    def test_changed_checkpoint_forces_a_new_attempt(self) -> None:
        with TemporaryDirectory() as directory:
            runner = StageRunner(Path(directory) / "work")
            first = runner.run(
                product="armenia",
                stage="splitter",
                command=_write_command(),
                expected_outputs=["result.txt"],
            )
            output = runner.builds_root / first.build_id / "splitter" / "result.txt"
            output.write_text("tampered", encoding="utf-8")
            second = runner.run(
                product="armenia",
                stage="splitter",
                command=_write_command(),
                build_id=first.build_id,
                expected_outputs=["result.txt"],
            )
            self.assertEqual(second.status, "success")
            self.assertEqual(output.read_text(encoding="utf-8"), "ok")

    def test_nonzero_exit_and_missing_checkpoint_are_failures(self) -> None:
        with TemporaryDirectory() as directory:
            runner = StageRunner(Path(directory) / "work")
            failed = runner.run(
                product="armenia",
                stage="splitter",
                command=[sys.executable, "-c", "raise SystemExit(7)"],
            )
            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed.exit_code, 7)

            missing = runner.run(
                product="armenia",
                stage="mkgmap",
                command=[sys.executable, "-c", "pass"],
                build_id=failed.build_id,
                expected_outputs=["map.img"],
            )
            self.assertEqual(missing.status, "failed")
            attempt = runner.history.attempts(failed.build_id)[-1]
            self.assertIn("checkpoint output is missing", attempt["error"])

    def test_output_path_cannot_escape_stage_workspace(self) -> None:
        with TemporaryDirectory() as directory:
            runner = StageRunner(Path(directory) / "work")
            with self.assertRaises(StageError):
                runner.run(
                    product="armenia",
                    stage="splitter",
                    command=_write_command(),
                    expected_outputs=["../outside"],
                )


if __name__ == "__main__":
    unittest.main()

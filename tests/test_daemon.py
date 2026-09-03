from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.daemon import _interrupt_running_builds, _select_due, _sleep_timeout
from uralla_build.history import HistoryStore
from uralla_build.scheduler import QueueItem


class DaemonTests(unittest.TestCase):
    def _item(self, product: str, *, due: bool = True) -> QueueItem:
        return QueueItem(
            product=product,
            priority=100,
            update_interval_days=7,
            last_success_at=None,
            due_at=None,
            due=due,
            never_built=True,
            overdue_seconds=None,
        )

    def test_select_due_skips_product_in_failure_backoff(self) -> None:
        items = [self._item("first"), self._item("second")]
        selected = _select_due(items, {"first": 150.0}, 100.0)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.product, "second")

    def test_sleep_timeout_uses_earliest_retry(self) -> None:
        items = [self._item("first"), self._item("second")]
        timeout = _sleep_timeout(
            items,
            {"first": 150.0, "second": 180.0},
            100.0,
            300.0,
        )
        self.assertEqual(timeout, 50.0)

    def test_stale_running_build_is_closed_as_interrupted(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            history = HistoryStore(root / "history.sqlite3")
            build_id = history.create_build("demo")
            stage_root = root / "stage"
            stage_root.mkdir()
            attempt_id = history.begin_attempt(
                build_id=build_id,
                stage_name="splitter",
                command=["true"],
                cwd=stage_root,
                stdout_log=stage_root / "stdout.log",
                stderr_log=stage_root / "stderr.log",
                resume_key="test",
            )

            recovered = _interrupt_running_builds(history, "daemon recovery")

            self.assertEqual(recovered, 1)
            build = history.get_build(build_id)
            self.assertIsNotNone(build)
            self.assertEqual(build["status"], "interrupted")
            attempt = next(
                item for item in history.attempts(build_id) if item["attempt_id"] == attempt_id
            )
            self.assertEqual(attempt["status"], "interrupted")
            self.assertEqual(attempt["exit_code"], 130)
            self.assertEqual(attempt["error"], "daemon recovery")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from uralla_build.scheduler import build_queue, next_due_product


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _manifest() -> dict[str, object]:
    return {
        "defaults": {"enabled": True, "priority": 100, "update_interval_days": None},
        "products": {
            "alpha": {},
            "beta": {},
            "urgent": {"priority": 10, "update_interval_days": 7},
            "disabled": {"enabled": False},
        },
    }


class SchedulerTests(unittest.TestCase):
    def test_priority_precedes_never_built_and_age(self) -> None:
        queue = build_queue(
            _manifest(),
            {"urgent": "2026-08-01T00:00:00+00:00"},
            now=NOW,
        )
        self.assertEqual([item.product for item in queue], ["urgent", "alpha", "beta"])
        self.assertEqual(next_due_product(queue).product, "urgent")

    def test_never_built_then_oldest_within_same_priority(self) -> None:
        queue = build_queue(
            _manifest(),
            {
                "alpha": "2026-08-20T00:00:00+00:00",
                "urgent": "2026-08-24T00:00:00+00:00",
            },
            now=NOW,
        )
        self.assertEqual([item.product for item in queue], ["urgent", "beta", "alpha"])
        self.assertFalse(queue[0].due)
        self.assertEqual(next_due_product(queue).product, "beta")

    def test_running_product_is_excluded(self) -> None:
        queue = build_queue(_manifest(), {}, {"urgent", "alpha"}, now=NOW)
        self.assertEqual([item.product for item in queue], ["beta"])


if __name__ == "__main__":
    unittest.main()

"""Deterministic product queue: priority first, overdue age second."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from .errors import ManifestError


@dataclass(frozen=True, slots=True)
class QueueItem:
    product: str
    priority: int
    update_interval_days: int | None
    last_success_at: str | None
    due_at: str | None
    due: bool
    never_built: bool
    overdue_seconds: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError(f"invalid history timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ManifestError(f"history timestamp has no timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def build_queue(
    manifest: Mapping[str, object],
    last_success_by_product: Mapping[str, str],
    running_products: set[str] | None = None,
    *,
    now: datetime | None = None,
) -> list[QueueItem]:
    """Rank enabled, non-running products without mutating history."""

    defaults = manifest.get("defaults")
    products = manifest.get("products")
    if not isinstance(defaults, Mapping) or not isinstance(products, Mapping):
        raise ManifestError("manifest defaults/products must be mappings")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    running = running_products or set()
    default_enabled = defaults.get("enabled", True)
    default_priority = defaults.get("priority", 100)
    default_interval = defaults.get("update_interval_days")
    queue: list[QueueItem] = []

    for key, raw in products.items():
        if not isinstance(raw, Mapping):
            continue
        product = str(key)
        if not raw.get("enabled", default_enabled) or product in running:
            continue
        priority = raw.get("priority", default_priority)
        interval = raw.get("update_interval_days", default_interval)
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0:
            raise ManifestError(f"products.{product}.priority must be a non-negative integer")
        if interval is not None and (
            not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0
        ):
            raise ManifestError(
                f"products.{product}.update_interval_days must be null or a positive integer"
            )

        last_text = last_success_by_product.get(product)
        if last_text is None:
            item = QueueItem(product, priority, interval, None, None, True, True, None)
        else:
            last = _parse_timestamp(last_text)
            if interval is None:
                due_at = None
                overdue = max(0.0, (current - last).total_seconds())
                due = True
            else:
                deadline = last + timedelta(days=interval)
                due_at = deadline.isoformat(timespec="seconds")
                overdue = (current - deadline).total_seconds()
                due = overdue >= 0
            item = QueueItem(
                product,
                priority,
                interval,
                last.isoformat(timespec="seconds"),
                due_at,
                due,
                False,
                overdue,
            )
        queue.append(item)

    queue.sort(
        key=lambda item: (
            item.priority,
            0 if item.never_built else 1,
            -(item.overdue_seconds or 0.0),
            item.product,
        )
    )
    return queue


def next_due_product(queue: list[QueueItem]) -> QueueItem | None:
    return next((item for item in queue if item.due), None)

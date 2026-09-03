"""Public human-readable map update schedule derived from manifest/history/scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from .history import HistoryStore
from .host import HostConfig
from .scheduler import QueueItem, build_queue

STATUS_FILENAME = "map-update-status.txt"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: str | None) -> str:
    parsed = _parse_timestamp(value)
    return parsed.strftime("%d.%m.%Y %H:%M") if parsed is not None else "—"


def _format_delta(seconds: float | None, *, never: bool) -> str:
    if never:
        return "первая сборка"
    if seconds is None:
        return "—"
    overdue = seconds >= 0
    total = max(int(abs(seconds)), 0)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        value = f"{days}д {hours:02d}ч"
    elif hours:
        value = f"{hours}ч {minutes:02d}м"
    else:
        value = f"{minutes}м"
    return f"просрочено {value}" if overdue else f"осталось {value}"


def _display_name(product_key: str, raw_product: object) -> str:
    if isinstance(raw_product, Mapping):
        names = raw_product.get("names")
        if isinstance(names, Mapping):
            family = names.get("family")
            if isinstance(family, str) and family:
                return family
    return product_key


def _state(item: QueueItem | None, latest_status: str | None, *, running: bool) -> str:
    if running:
        return "собирается"
    if latest_status == "failed":
        return "ошибка"
    if item is None:
        return "—"
    return "ожидает обновления" if item.due else "актуальна"


def render_map_update_status(
    manifest: Mapping[str, object],
    history: HistoryStore,
    *,
    now: datetime | None = None,
) -> str:
    """Render one UTF-8 table from the canonical scheduler/history snapshot."""

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    last_success = history.latest_success_by_product()
    running = history.running_products()
    latest = history.latest_build_by_product()
    queue = build_queue(manifest, last_success, running, now=current)
    queue_by_product = {item.product: item for item in queue}

    products = manifest.get("products")
    defaults = manifest.get("defaults")
    raw_products = products if isinstance(products, Mapping) else {}
    default_enabled = defaults.get("enabled", True) if isinstance(defaults, Mapping) else True

    rows: list[tuple[str, str, str, str, str]] = []
    for product_key, raw_product in raw_products.items():
        product = str(product_key)
        if isinstance(raw_product, Mapping) and not raw_product.get("enabled", default_enabled):
            continue
        item = queue_by_product.get(product)
        is_running = product in running
        latest_row = latest.get(product, {})
        latest_status = str(latest_row.get("status")) if latest_row else None
        last_text = last_success.get(product)

        if is_running:
            # Running products are intentionally absent from scheduler.build_queue,
            # so reconstruct only their TTL columns from the same manifest values.
            interval = None
            if isinstance(raw_product, Mapping):
                interval = raw_product.get("update_interval_days")
            if interval is None and isinstance(defaults, Mapping):
                interval = defaults.get("update_interval_days")
            if last_text and isinstance(interval, int) and interval > 0:
                last_dt = _parse_timestamp(last_text)
                due_at = last_dt.replace(microsecond=0) + timedelta(days=interval) if last_dt else None
                due_text = due_at.isoformat() if due_at is not None else None
                overdue_seconds = (current - due_at).total_seconds() if due_at is not None else None
                never = False
            else:
                due_text = None
                overdue_seconds = None
                never = last_text is None
        elif item is not None:
            due_text = item.due_at
            overdue_seconds = item.overdue_seconds
            never = item.never_built
        else:
            due_text = None
            overdue_seconds = None
            never = last_text is None

        next_text = "первая сборка" if never else _format_timestamp(due_text)
        rows.append(
            (
                _display_name(product, raw_product),
                _format_timestamp(last_text),
                next_text,
                _format_delta(overdue_seconds, never=never),
                _state(item, latest_status, running=is_running),
            )
        )

    headers = ("Карта", "Последняя публикация", "≈ Следующее обновление", "Срок", "Состояние")
    widths = [len(headers[index]) for index in range(len(headers))]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def line(values: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values)).rstrip()

    separator = "  ".join("─" * width for width in widths)
    lines = [
        "Сроки обновления Garmin-карт",
        f"Сформировано: {current.strftime('%d.%m.%Y %H:%M')} UTC",
        "Время следующего обновления ориентировочное: очередь может сдвигаться из-за длительности сборок,",
        "обновления исходных OSM-данных, ручного приоритета или ошибки.",
        "",
        line(headers),
        separator,
    ]
    lines.extend(line(row) for row in rows)
    lines.append("")
    return "\n".join(lines)


def write_map_update_status(
    manifest: Mapping[str, object],
    host: HostConfig,
    *,
    now: datetime | None = None,
) -> Path:
    """Atomically replace output/map-update-status.txt."""

    history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
    target = host.paths.publish_root / STATUS_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.partial")
    text = render_map_update_status(manifest, history, now=now)
    try:
        temporary.write_text(text, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target

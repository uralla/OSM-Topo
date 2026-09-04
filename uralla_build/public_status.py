"""Public map update status derived from manifest/history/scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path, PurePosixPath
from typing import Mapping
from uuid import uuid4

from .history import HistoryStore
from .host import HostConfig
from .map_recipe import map_recipe_fingerprint
from .publish import gmapi_zip_name
from .scheduler import QueueItem, build_queue

STATUS_FILENAME = "map-update-status.txt"
STATUS_JSON_FILENAME = "map-update-status.json"
STATUS_JSON_SCHEMA_VERSION = 1
_STATUS_NOTE = (
    "Время следующего обновления ориентировочное: очередь может сдвигаться из-за "
    "длительности сборок, обновления исходных OSM-данных, ручного приоритета или ошибки."
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_timestamp(value: str | None) -> str | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


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
        web = raw_product.get("web")
        if isinstance(web, Mapping):
            title = web.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
        names = raw_product.get("names")
        if isinstance(names, Mapping):
            family = names.get("family")
            if isinstance(family, str) and family:
                return family
    return product_key


def _web_visible(raw_product: object) -> bool:
    if not isinstance(raw_product, Mapping):
        return False
    web = raw_product.get("web")
    return isinstance(web, Mapping) and web.get("visible") is True


def _web_order(raw_product: object, fallback: int) -> int:
    if isinstance(raw_product, Mapping):
        web = raw_product.get("web")
        if isinstance(web, Mapping):
            value = web.get("order")
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
    return fallback


def _state_code(item: QueueItem | None, latest_status: str | None, *, running: bool) -> str:
    if running:
        return "building"
    if latest_status == "failed":
        return "error"
    if latest_status == "interrupted":
        return "interrupted"
    if item is None:
        return "unknown"
    return "due" if item.due else "current"


_STATE_LABELS = {
    "building": "собирается",
    "error": "ошибка",
    "interrupted": "прервано",
    "due": "ожидает обновления",
    "current": "актуальна",
    "unknown": "—",
}


def _relative_public_path(subdir: str, filename: str) -> str:
    base = PurePosixPath(subdir)
    if str(base) in {"", "."}:
        return filename
    return (base / filename).as_posix()


def _artifact_info(root: Path, relative_path: str) -> dict[str, object]:
    path = root / Path(relative_path)
    if not path.is_file():
        return {
            "filename": path.name,
            "url": relative_path,
            "available": False,
            "size": None,
        }
    size = path.stat().st_size
    return {
        "filename": path.name,
        "url": relative_path,
        "available": size > 0,
        "size": size if size > 0 else None,
    }


def _latest_success_recipes(history: HistoryStore) -> dict[str, str | None]:
    with history.connect() as connection:
        rows = connection.execute(
            """SELECT b.product, b.metadata_json
               FROM builds AS b
               WHERE b.status = 'success'
                 AND b.finished_at IS NOT NULL
                 AND b.rowid = (
                     SELECT b2.rowid FROM builds AS b2
                     WHERE b2.product = b.product
                       AND b2.status = 'success'
                       AND b2.finished_at IS NOT NULL
                     ORDER BY b2.finished_at DESC, b2.rowid DESC
                     LIMIT 1
                 )"""
        ).fetchall()
    result: dict[str, str | None] = {}
    for row in rows:
        try:
            metadata = json.loads(str(row["metadata_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        recipe = metadata.get("map_recipe") if isinstance(metadata, dict) else None
        result[str(row["product"])] = recipe if isinstance(recipe, str) and recipe else None
    return result


def _recipe_state(current_recipe: str, previous_recipe: str | None, *, never: bool) -> str:
    if never:
        return "legacy"
    if previous_recipe is None:
        return "legacy"
    return "current" if previous_recipe == current_recipe else "stale"


def _schedule_values(
    raw_product: object,
    defaults: object,
    item: QueueItem | None,
    *,
    is_running: bool,
    last_text: str | None,
    current: datetime,
) -> tuple[str | None, float | None, bool]:
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
            due_at = (
                last_dt.replace(microsecond=0) + timedelta(days=interval)
                if last_dt
                else None
            )
            due_text = due_at.isoformat() if due_at is not None else None
            overdue_seconds = (
                (current - due_at).total_seconds() if due_at is not None else None
            )
            return due_text, overdue_seconds, False
        return None, None, last_text is None
    if item is not None:
        return item.due_at, item.overdue_seconds, item.never_built
    return None, None, last_text is None


def build_public_status_snapshot(
    manifest: Mapping[str, object],
    history: HistoryStore,
    host: HostConfig | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Build the canonical public status snapshot used by TXT and JSON views."""

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    last_success = history.latest_success_by_product()
    last_recipes = _latest_success_recipes(history)
    running = history.running_products()
    latest = history.latest_build_by_product()
    queue = build_queue(manifest, last_success, running, now=current)
    queue_by_product = {item.product: item for item in queue}

    products = manifest.get("products")
    defaults = manifest.get("defaults")
    raw_products = products if isinstance(products, Mapping) else {}
    default_enabled = defaults.get("enabled", True) if isinstance(defaults, Mapping) else True

    rows: list[dict[str, object]] = []
    for manifest_index, (product_key, raw_product) in enumerate(raw_products.items()):
        product = str(product_key)
        if isinstance(raw_product, Mapping) and not raw_product.get("enabled", default_enabled):
            continue
        item = queue_by_product.get(product)
        is_running = product in running
        latest_row = latest.get(product, {})
        latest_status = str(latest_row.get("status")) if latest_row else None
        last_text = last_success.get(product)
        due_text, overdue_seconds, never = _schedule_values(
            raw_product,
            defaults,
            item,
            is_running=is_running,
            last_text=last_text,
            current=current,
        )
        state_code = _state_code(item, latest_status, running=is_running)
        current_recipe = map_recipe_fingerprint(manifest, product)
        row: dict[str, object] = {
            "product": product,
            "title": _display_name(product, raw_product),
            "web_visible": _web_visible(raw_product),
            "web_order": _web_order(raw_product, 1_000_000 + manifest_index),
            "state": state_code,
            "state_label": _STATE_LABELS[state_code],
            "recipe_state": _recipe_state(current_recipe, last_recipes.get(product), never=never),
            "last_publication": _iso_timestamp(last_text),
            "next_update": None if never else _iso_timestamp(due_text),
            "never_built": never,
            "overdue_seconds": overdue_seconds,
        }

        names = raw_product.get("names") if isinstance(raw_product, Mapping) else None
        output_img = names.get("output_img") if isinstance(names, Mapping) else None
        if host is not None and isinstance(output_img, str) and output_img:
            img_relative = _relative_public_path(host.publication.img_subdir, output_img)
            basecamp_relative = _relative_public_path(
                host.publication.gmapi_subdir, gmapi_zip_name(output_img)
            )
            row["img"] = _artifact_info(host.paths.publish_root, img_relative)
            row["basecamp"] = _artifact_info(host.paths.publish_root, basecamp_relative)
        rows.append(row)

    return {
        "schema_version": STATUS_JSON_SCHEMA_VERSION,
        "generated_at": current.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "timezone": "UTC",
        "note": _STATUS_NOTE,
        "products": rows,
    }


def _render_snapshot_text(snapshot: Mapping[str, object]) -> str:
    generated_at = _parse_timestamp(str(snapshot.get("generated_at", "")))
    raw_products = snapshot.get("products")
    products = raw_products if isinstance(raw_products, list) else []
    rows: list[tuple[str, str, str, str, str]] = []
    for raw_row in products:
        row = raw_row if isinstance(raw_row, Mapping) else {}
        never = bool(row.get("never_built"))
        next_update = row.get("next_update")
        next_text = "первая сборка" if never else _format_timestamp(
            str(next_update) if next_update else None
        )
        overdue = row.get("overdue_seconds")
        overdue_seconds = float(overdue) if isinstance(overdue, (int, float)) else None
        rows.append(
            (
                str(row.get("title", "—")),
                _format_timestamp(
                    str(row.get("last_publication")) if row.get("last_publication") else None
                ),
                next_text,
                _format_delta(overdue_seconds, never=never),
                str(row.get("state_label", "—")),
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
    generated_text = generated_at.strftime("%d.%m.%Y %H:%M") if generated_at else "—"
    lines = [
        "Сроки обновления Garmin-карт",
        f"Сформировано: {generated_text} UTC",
        "Время следующего обновления ориентировочное: очередь может сдвигаться из-за длительности сборок,",
        "обновления исходных OSM-данных, ручного приоритета или ошибки.",
        "",
        line(headers),
        separator,
    ]
    lines.extend(line(row) for row in rows)
    lines.append("")
    return "\n".join(lines)


def render_map_update_status(
    manifest: Mapping[str, object],
    history: HistoryStore,
    *,
    now: datetime | None = None,
) -> str:
    """Render one UTF-8 table from the canonical public status snapshot."""

    return _render_snapshot_text(build_public_status_snapshot(manifest, history, now=now))


def _public_json(snapshot: Mapping[str, object]) -> dict[str, object]:
    raw_products = snapshot.get("products")
    products = raw_products if isinstance(raw_products, list) else []
    visible: list[dict[str, object]] = []
    for raw_row in products:
        if not isinstance(raw_row, Mapping) or raw_row.get("web_visible") is not True:
            continue
        row = dict(raw_row)
        row.pop("web_visible", None)
        row.pop("web_order", None)
        visible.append(row)
    visible.sort(
        key=lambda row: (
            _web_sort_order(snapshot, str(row.get("product", ""))),
            str(row.get("title", "")).casefold(),
        )
    )
    return {
        "schema_version": snapshot.get("schema_version"),
        "generated_at": snapshot.get("generated_at"),
        "timezone": snapshot.get("timezone"),
        "note": snapshot.get("note"),
        "products": visible,
    }


def _web_sort_order(snapshot: Mapping[str, object], product: str) -> int:
    raw_products = snapshot.get("products")
    products = raw_products if isinstance(raw_products, list) else []
    for row in products:
        if isinstance(row, Mapping) and row.get("product") == product:
            order = row.get("web_order")
            if isinstance(order, int) and not isinstance(order, bool):
                return order
    return 1_000_000


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.partial")
    try:
        temporary.write_bytes(payload)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_map_update_status(
    manifest: Mapping[str, object],
    host: HostConfig,
    *,
    now: datetime | None = None,
) -> Path:
    """Atomically replace public TXT and JSON status files."""

    history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
    snapshot = build_public_status_snapshot(manifest, history, host, now=now)
    text_target = host.paths.publish_root / STATUS_FILENAME
    json_target = host.paths.publish_root / STATUS_JSON_FILENAME

    _atomic_write(text_target, _render_snapshot_text(snapshot).encode("utf-8"))
    json_payload = json.dumps(
        _public_json(snapshot),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    ) + "\n"
    _atomic_write(json_target, json_payload.encode("utf-8"))
    return text_target

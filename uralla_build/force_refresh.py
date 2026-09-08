"""Persistent one-shot forced refresh queue shared by menu and daemon."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .errors import StageError


SCHEMA_VERSION = 1
STATE_FILENAME = "daemon-force-refresh.json"


@dataclass(frozen=True, slots=True)
class ForcedRefreshState:
    requested_at: str
    products: tuple[str, ...]


def forced_refresh_state_path(work_root: str | Path) -> Path:
    return Path(work_root) / "state" / STATE_FILENAME


def load_forced_refresh(path: str | Path) -> ForcedRefreshState | None:
    source = Path(path)
    if not source.is_file():
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageError(f"cannot load forced-refresh state {source}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise StageError(f"unsupported forced-refresh state: {source}")
    requested_at = payload.get("requested_at")
    products = payload.get("products")
    if (
        not isinstance(requested_at, str)
        or not requested_at
        or not isinstance(products, list)
        or not products
        or any(not isinstance(product, str) or not product for product in products)
    ):
        raise StageError(f"invalid forced-refresh state: {source}")
    return ForcedRefreshState(
        requested_at=requested_at,
        products=tuple(dict.fromkeys(products)),
    )


def write_forced_refresh(
    path: str | Path,
    *,
    requested_at: str,
    products: Iterable[str],
) -> ForcedRefreshState:
    ordered = tuple(dict.fromkeys(str(product) for product in products if str(product)))
    if not ordered:
        raise StageError("forced-refresh queue is empty")
    state = ForcedRefreshState(requested_at=requested_at, products=ordered)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.partial")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "requested_at": state.requested_at,
        "products": list(state.products),
    }
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return state


def clear_forced_refresh(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)

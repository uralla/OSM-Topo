from datetime import datetime, timezone

from uralla_build.history import HistoryStore
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy
from uralla_build.public_status import render_map_update_status, write_map_update_status


def _manifest():
    return {
        "defaults": {"enabled": True, "priority": 100, "update_interval_days": 7},
        "products": {
            "fresh": {
                "names": {"family": "Fresh.OSM"},
                "update_interval_days": 14,
            },
            "failed": {
                "names": {"family": "Failed.OSM"},
                "update_interval_days": 7,
            },
            "running": {
                "names": {"family": "Running.OSM"},
                "update_interval_days": 7,
            },
        },
    }


def _insert_build(history, build_id, product, status, created_at, finished_at=None):
    with history.connect() as connection:
        connection.execute(
            "INSERT INTO builds(build_id, product, status, created_at, finished_at, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, '{}')",
            (build_id, product, status, created_at, finished_at),
        )


def test_public_status_uses_success_ttl_and_latest_build_state(tmp_path):
    history = HistoryStore(tmp_path / "state" / "history.sqlite3")
    _insert_build(
        history,
        "fresh-success",
        "fresh",
        "success",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T11:00:00+00:00",
    )
    _insert_build(
        history,
        "failed-build",
        "failed",
        "failed",
        "2026-09-03T09:00:00+00:00",
        "2026-09-03T09:01:00+00:00",
    )
    _insert_build(
        history,
        "running-build",
        "running",
        "running",
        "2026-09-03T09:30:00+00:00",
    )

    text = render_map_update_status(
        _manifest(),
        history,
        now=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )

    assert "Сформировано: 03.09.2026 10:00 UTC" in text
    assert "Fresh.OSM" in text
    assert "01.09.2026 11:00" in text
    assert "15.09.2026 11:00" in text
    assert "актуальна" in text
    assert "Failed.OSM" in text
    assert "ошибка" in text
    assert "Running.OSM" in text
    assert "собирается" in text
    assert "первая сборка" in text


def test_public_status_write_is_atomic_and_utf8(tmp_path):
    work = tmp_path / "work"
    output = tmp_path / "output"
    host = HostConfig(
        HostPaths(tmp_path / "data", work, output, tmp_path / "tools", tmp_path / "dem"),
        PublicationPolicy(".", "mapsource", False, "store", False),
        1,
        20,
    )
    history = HistoryStore(work / "state" / "history.sqlite3")
    _insert_build(
        history,
        "fresh-success",
        "fresh",
        "success",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T11:00:00+00:00",
    )

    target = write_map_update_status(
        _manifest(),
        host,
        now=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )

    assert target == output / "map-update-status.txt"
    assert "Сроки обновления Garmin-карт" in target.read_text(encoding="utf-8")
    assert not list(output.glob(".map-update-status.txt.*.partial"))

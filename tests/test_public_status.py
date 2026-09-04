import json
from datetime import datetime, timezone

from uralla_build.history import HistoryStore
from uralla_build.host import HostConfig, HostPaths, PublicationPolicy
from uralla_build.public_status import (
    build_public_status_snapshot,
    render_map_update_status,
    write_map_update_status,
)


def _manifest():
    return {
        "defaults": {"enabled": True, "priority": 100, "update_interval_days": 7},
        "products": {
            "fresh": {
                "names": {"family": "Fresh.OSM", "output_img": "Fresh.OSM.img"},
                "web": {"title": "Свежая карта", "order": 20, "visible": True},
                "update_interval_days": 14,
            },
            "failed": {
                "names": {"family": "Failed.OSM", "output_img": "Failed.OSM.img"},
                "web": {"title": "Ошибка карты", "order": 30, "visible": True},
                "update_interval_days": 7,
            },
            "interrupted": {
                "names": {
                    "family": "Interrupted.OSM",
                    "output_img": "Interrupted.OSM.img",
                },
                "web": {"visible": False},
                "update_interval_days": 7,
            },
            "running": {
                "names": {"family": "Running.OSM", "output_img": "Running.OSM.img"},
                "web": {"title": "Собираемая карта", "order": 10, "visible": True},
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


def _host(tmp_path):
    return HostConfig(
        HostPaths(
            tmp_path / "data",
            tmp_path / "work",
            tmp_path / "output",
            tmp_path / "tools",
            tmp_path / "dem",
        ),
        PublicationPolicy(".", "mapsource", False, "store", False),
        1,
        20,
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
        "interrupted-build",
        "interrupted",
        "interrupted",
        "2026-09-03T09:15:00+00:00",
        "2026-09-03T09:16:00+00:00",
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
    assert "Свежая карта" in text
    assert "01.09.2026 11:00" in text
    assert "15.09.2026 11:00" in text
    assert "актуальна" in text
    assert "Ошибка карты" in text
    assert "ошибка" in text
    assert "Interrupted.OSM" in text
    assert "прервано" in text
    assert "Собираемая карта" in text
    assert "собирается" in text
    assert "первая сборка" in text


def test_snapshot_keeps_running_product_downloadable(tmp_path):
    host = _host(tmp_path)
    history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
    _insert_build(
        history,
        "running-build",
        "running",
        "running",
        "2026-09-03T09:30:00+00:00",
    )
    host.paths.publish_root.mkdir(parents=True)
    (host.paths.publish_root / "Running.OSM.img").write_bytes(b"img-current")
    mapsource = host.paths.publish_root / "mapsource"
    mapsource.mkdir()
    (mapsource / "Running.OSM-ms.zip").write_bytes(b"gmapi-current")

    snapshot = build_public_status_snapshot(
        _manifest(),
        history,
        host,
        now=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )
    running = next(row for row in snapshot["products"] if row["product"] == "running")

    assert running["state"] == "building"
    assert running["img"] == {
        "filename": "Running.OSM.img",
        "url": "Running.OSM.img",
        "available": True,
        "size": len(b"img-current"),
    }
    assert running["basecamp"] == {
        "filename": "Running.OSM-ms.zip",
        "url": "mapsource/Running.OSM-ms.zip",
        "available": True,
        "size": len(b"gmapi-current"),
    }


def test_public_status_writes_atomic_utf8_txt_and_filtered_json(tmp_path):
    host = _host(tmp_path)
    history = HistoryStore(host.paths.work_root / "state" / "history.sqlite3")
    _insert_build(
        history,
        "fresh-success",
        "fresh",
        "success",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T11:00:00+00:00",
    )
    output = host.paths.publish_root
    output.mkdir(parents=True)
    (output / "Fresh.OSM.img").write_bytes(b"fresh-img")

    target = write_map_update_status(
        _manifest(),
        host,
        now=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )

    assert target == output / "map-update-status.txt"
    assert "Сроки обновления Garmin-карт" in target.read_text(encoding="utf-8")
    json_target = output / "map-update-status.json"
    payload = json.loads(json_target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["generated_at"] == "2026-09-03T10:00:00Z"
    assert [row["product"] for row in payload["products"]] == [
        "running",
        "fresh",
        "failed",
    ]
    fresh = payload["products"][1]
    assert fresh["title"] == "Свежая карта"
    assert fresh["img"]["available"] is True
    assert fresh["img"]["size"] == len(b"fresh-img")
    assert fresh["basecamp"]["available"] is False
    assert fresh["basecamp"]["url"] == "mapsource/Fresh.OSM-ms.zip"
    assert not list(output.glob(".map-update-status.txt.*.partial"))
    assert not list(output.glob(".map-update-status.json.*.partial"))

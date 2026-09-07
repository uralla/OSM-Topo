from pathlib import Path

from uralla_build.entrypoint import _test_source_exists
from uralla_build.host import HostConfig, HostPaths


def _host(tmp_path: Path) -> HostConfig:
    return HostConfig(
        paths=HostPaths(
            data_root=tmp_path,
            work_root=tmp_path / "work",
            publish_root=tmp_path / "publish",
            tools_root=tmp_path / "tools",
            dem_root=tmp_path / "dem",
        ),
        preprocess_concurrency=1,
    )


def test_test_product_accepts_existing_local_source_regardless_of_age(tmp_path: Path) -> None:
    manifest = {
        "sources": {"russia": {"path": "input/russia-latest.osm.pbf"}},
        "products": {
            "test": {"source": "russia"},
            "ural-s": {"source": "russia"},
        },
    }
    source = tmp_path / "input" / "russia-latest.osm.pbf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"local-test-source")

    host = _host(tmp_path)

    assert _test_source_exists(manifest, host, "test") is True
    assert _test_source_exists(manifest, host, "ural-s") is False

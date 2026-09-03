from pathlib import Path

from uralla_build.daemon import _build_command


def test_daemon_build_command_uses_package_entrypoint(monkeypatch):
    monkeypatch.setattr("uralla_build.daemon.sys.executable", "/venv/bin/python")

    command = _build_command(
        repo_root=Path("/repo"),
        manifest_path=Path("/repo/config/maps.yaml"),
        host_path=Path("/work/host.yaml"),
        tools_lock_path=Path("/repo/config/tools.lock.yaml"),
        product="armenia",
    )

    assert command[:3] == ["/venv/bin/python", "-m", "uralla_build"]
    assert "uralla_build.entrypoint" not in command
    assert command[-3:] == ["--tools-lock", "/repo/config/tools.lock.yaml", "--apply"]
    assert "build-product" in command
    assert "armenia" in command

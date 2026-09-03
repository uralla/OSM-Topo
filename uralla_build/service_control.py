"""Small systemd control layer for the interactive workspace launcher."""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess


SERVICE_NAME = "uralla-build-daemon.service"


@dataclass(frozen=True)
class ServiceState:
    available: bool
    installed: bool
    active: bool
    state: str


def systemd_available() -> bool:
    return shutil.which("systemctl") is not None


def service_state() -> ServiceState:
    if not systemd_available():
        return ServiceState(False, False, False, "UNAVAILABLE")

    load = subprocess.run(
        ["systemctl", "show", SERVICE_NAME, "--property=LoadState", "--value"],
        text=True,
        capture_output=True,
        check=False,
    )
    load_state = load.stdout.strip()
    installed = load.returncode == 0 and load_state not in {"", "not-found"}
    if not installed:
        return ServiceState(True, False, False, "NOT INSTALLED")

    active = subprocess.run(
        ["systemctl", "is-active", SERVICE_NAME],
        text=True,
        capture_output=True,
        check=False,
    )
    state = active.stdout.strip() or "unknown"
    return ServiceState(True, True, active.returncode == 0 and state == "active", state.upper())


def _privileged_command(*args: str) -> list[str]:
    command = ["systemctl", *args, SERVICE_NAME]
    if os.geteuid() == 0:
        return command
    if shutil.which("sudo") is not None:
        return ["sudo", *command]
    return command


def run_service_action(action: str) -> int:
    if action not in {"start", "stop", "restart"}:
        raise ValueError(f"unsupported daemon service action: {action}")
    if not systemd_available():
        return 127
    return int(subprocess.run(_privileged_command(action), check=False).returncode)


def run_service_status() -> int:
    if not systemd_available():
        return 127
    return int(
        subprocess.run(
            ["systemctl", "status", SERVICE_NAME, "--no-pager"],
            check=False,
        ).returncode
    )


def run_service_log(*, follow: bool = False, lines: int = 80) -> int:
    if shutil.which("journalctl") is None:
        return 127
    command = ["journalctl", "-u", SERVICE_NAME]
    if follow:
        command.append("-f")
    else:
        command.extend(("-n", str(lines), "--no-pager"))
    return int(subprocess.run(command, check=False).returncode)

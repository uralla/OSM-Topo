from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from uralla_build import service_control


class ServiceControlTests(unittest.TestCase):
    def test_missing_systemd_reports_unavailable(self) -> None:
        with patch("uralla_build.service_control.shutil.which", return_value=None):
            state = service_control.service_state()
        self.assertFalse(state.available)
        self.assertFalse(state.installed)
        self.assertFalse(state.active)
        self.assertEqual(state.state, "UNAVAILABLE")

    def test_missing_unit_reports_not_installed(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="not-found\n", stderr="")
        with patch("uralla_build.service_control.shutil.which", return_value="/bin/systemctl"), patch(
            "uralla_build.service_control.subprocess.run", return_value=completed
        ):
            state = service_control.service_state()
        self.assertTrue(state.available)
        self.assertFalse(state.installed)
        self.assertEqual(state.state, "NOT INSTALLED")

    def test_active_unit_is_detected(self) -> None:
        responses = [
            subprocess.CompletedProcess([], 0, stdout="loaded\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="active\n", stderr=""),
        ]
        with patch("uralla_build.service_control.shutil.which", return_value="/bin/systemctl"), patch(
            "uralla_build.service_control.subprocess.run", side_effect=responses
        ):
            state = service_control.service_state()
        self.assertTrue(state.installed)
        self.assertTrue(state.active)
        self.assertEqual(state.state, "ACTIVE")

    def test_service_actions_use_systemctl_and_sudo_for_normal_user(self) -> None:
        completed = subprocess.CompletedProcess([], 0)
        with patch("uralla_build.service_control.shutil.which", side_effect=lambda name: f"/bin/{name}"), patch(
            "uralla_build.service_control.os.geteuid", return_value=1000
        ), patch("uralla_build.service_control.subprocess.run", return_value=completed) as run:
            code = service_control.run_service_action("restart")
        self.assertEqual(code, 0)
        run.assert_called_once_with(
            ["sudo", "systemctl", "restart", service_control.SERVICE_NAME],
            check=False,
        )

    def test_log_reader_uses_journalctl(self) -> None:
        completed = subprocess.CompletedProcess([], 0)
        with patch("uralla_build.service_control.shutil.which", return_value="/bin/journalctl"), patch(
            "uralla_build.service_control.subprocess.run", return_value=completed
        ) as run:
            code = service_control.run_service_log(lines=40)
        self.assertEqual(code, 0)
        run.assert_called_once_with(
            ["journalctl", "-u", service_control.SERVICE_NAME, "-n", "40", "--no-pager"],
            check=False,
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from uralla_build import interactive
from uralla_build.service_control import ServiceState


class InteractiveStartControlsTests(unittest.TestCase):
    def test_main_menu_advertises_status_and_daemon_controls(self) -> None:
        source = Path(interactive.__file__).read_text(encoding="utf-8")
        self.assertIn('s  map status', source)
        self.assertIn('d  daemon', source)
        self.assertIn('if choice == "s":', source)
        self.assertIn('if choice == "d":', source)

    def test_map_status_uses_canonical_public_status_renderer(self) -> None:
        with patch("uralla_build.interactive.render_map_update_status", return_value="STATUS TABLE\n") as render, patch(
            "builtins.input", return_value=""
        ), patch("builtins.print") as output:
            manifest = {"products": {}}
            history = object()
            interactive._show_map_status(manifest, history)  # type: ignore[arg-type]
        render.assert_called_once_with(manifest, history)
        self.assertTrue(any("STATUS TABLE" in str(call) for call in output.call_args_list))

    def test_daemon_menu_does_not_try_to_install_missing_service(self) -> None:
        missing = ServiceState(True, False, False, "NOT INSTALLED")
        with patch("uralla_build.interactive.service_state", return_value=missing), patch(
            "builtins.input", return_value=""
        ), patch("uralla_build.interactive.run_service_action") as action, patch("builtins.print") as output:
            interactive._daemon_menu(Path("/repo"))
        action.assert_not_called()
        text = "\n".join(str(call) for call in output.call_args_list)
        self.assertIn("Service is not installed", text)
        self.assertIn("install-daemon-service.sh", text)


if __name__ == "__main__":
    unittest.main()

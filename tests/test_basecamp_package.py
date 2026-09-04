from __future__ import annotations

import unittest

from uralla_build.basecamp_package import basecamp_installer_files


class BaseCampPackageTests(unittest.TestCase):
    def test_payload_contains_install_uninstall_and_readme(self) -> None:
        files = basecamp_installer_files("Topo-Ural-N.gmap")
        self.assertEqual(
            set(files),
            {"install-map.cmd", "uninstall-map.cmd", "map-install.ps1", "README-INSTALL.txt"},
        )
        self.assertIn(b"-Action Install", files["install-map.cmd"])
        self.assertIn(b"-Action Uninstall", files["uninstall-map.cmd"])

    def test_powershell_is_user_scoped_and_registry_free(self) -> None:
        script = basecamp_installer_files("Topo-Ural-N.gmap")["map-install.ps1"].decode("utf-8")
        self.assertIn("$env:APPDATA", script)
        self.assertIn("'Garmin\\Maps'", script)
        self.assertIn("Get-Process -Name BaseCamp", script)
        self.assertNotIn("HKLM", script)
        self.assertNotIn("HKCU", script)
        self.assertNotIn("Set-ItemProperty", script)
        self.assertNotIn("Start-Process powershell", script)
        self.assertNotIn("RunAs", script)

    def test_install_stages_new_map_and_can_restore_previous_map(self) -> None:
        script = basecamp_installer_files("Topo-Ural-N.gmap")["map-install.ps1"].decode("utf-8")
        copy_pos = script.index("Copy-Item -LiteralPath $source.FullName")
        backup_pos = script.index("Move-Item -LiteralPath $target -Destination $backup")
        install_pos = script.index("Move-Item -LiteralPath $temporary -Destination $target")
        self.assertLess(copy_pos, backup_pos)
        self.assertLess(backup_pos, install_pos)
        self.assertIn("Move-Item -LiteralPath $backup -Destination $target", script)

    def test_readme_names_the_exact_gmap_directory(self) -> None:
        readme = basecamp_installer_files("Topo-Ural-N.gmap")["README-INSTALL.txt"].decode("utf-8")
        self.assertIn("Topo-Ural-N.gmap", readme)
        self.assertIn("%APPDATA%\\Garmin\\Maps\\Topo-Ural-N.gmap", readme)
        self.assertIn("Права администратора", readme)

    def test_rejects_non_gmap_or_path_names(self) -> None:
        for value in ("Topo-Ural-N", "../Topo-Ural-N.gmap", "folder\\Topo-Ural-N.gmap"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    basecamp_installer_files(value)


if __name__ == "__main__":
    unittest.main()

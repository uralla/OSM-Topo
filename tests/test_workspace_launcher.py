from __future__ import annotations

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from uralla_build.workspace import write_launcher


class WorkspaceLauncherTests(unittest.TestCase):
    def test_launcher_runs_from_repo_with_external_host_and_configured_python(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo with spaces"
            workspace = root / "workspace with spaces"
            repo.mkdir()
            workspace.mkdir()

            host = workspace / "host.yaml"
            host.write_text("schema_version: 1\n", encoding="utf-8")

            fake_python = workspace / "fake-python"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                "printf 'cwd=%s\\n' \"$PWD\"\n"
                "printf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            launcher = workspace / "uralla"
            write_launcher(launcher, repo, host, fake_python)

            self.assertTrue(launcher.is_file())
            self.assertTrue(launcher.stat().st_mode & 0o111)

            result = subprocess.run(
                [str(launcher), "build-product", "crimea", "--apply"],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=True,
            )
            lines = result.stdout.splitlines()
            self.assertIn(f"cwd={repo}", lines)
            self.assertIn("arg=-m", lines)
            self.assertIn("arg=uralla_build", lines)
            self.assertIn("arg=--host", lines)
            self.assertIn(f"arg={host}", lines)
            self.assertIn("arg=build-product", lines)
            self.assertIn("arg=crimea", lines)
            self.assertIn("arg=--apply", lines)

    def test_launcher_reports_missing_repository_cleanly(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "missing-repo"
            workspace = root / "workspace"
            workspace.mkdir()
            host = workspace / "host.yaml"
            host.write_text("schema_version: 1\n", encoding="utf-8")
            fake_python = workspace / "python"
            fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            launcher = workspace / "uralla"
            write_launcher(launcher, repo, host, fake_python)

            result = subprocess.run(
                [str(launcher), "doctor"],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("repository not found", result.stderr)
            self.assertIn("Run setup.sh again", result.stderr)


if __name__ == "__main__":
    unittest.main()

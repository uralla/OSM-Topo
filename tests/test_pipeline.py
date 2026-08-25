from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from uralla_build.pipeline import PipelineRunner, PipelineStage
from uralla_build.runner import StageRunner


def _write_stage(filename: str, content: str) -> PipelineStage:
    command = (
        sys.executable,
        "-c",
        "from pathlib import Path; "
        f"Path({filename!r}).write_text({content!r}, encoding='utf-8')",
    )
    return PipelineStage(filename.removesuffix(".txt"), command, (filename,))


class PipelineRunnerTests(unittest.TestCase):
    def test_success_marks_build_terminal(self) -> None:
        with TemporaryDirectory() as directory:
            stage_runner = StageRunner(Path(directory) / "work")
            result = PipelineRunner(stage_runner).run(
                product="armenia",
                stages=(_write_stage("extract.txt", "one"), _write_stage("splitter.txt", "two")),
            )

            self.assertEqual(result.status, "success")
            self.assertEqual([stage.status for stage in result.stages], ["success", "success"])
            build = stage_runner.history.get_build(result.build_id)
            self.assertIsNotNone(build)
            self.assertEqual(build["status"], "success")
            self.assertIsNotNone(build["finished_at"])

    def test_failed_stage_stops_pipeline_and_marks_build(self) -> None:
        with TemporaryDirectory() as directory:
            stage_runner = StageRunner(Path(directory) / "work")
            failing = PipelineStage(
                "transform",
                (sys.executable, "-c", "raise SystemExit(9)"),
            )
            result = PipelineRunner(stage_runner).run(
                product="armenia",
                stages=(failing, _write_stage("splitter.txt", "must not run")),
            )

            self.assertEqual(result.status, "failed")
            self.assertEqual(len(result.stages), 1)
            self.assertEqual(result.stages[0].exit_code, 9)
            build = stage_runner.history.get_build(result.build_id)
            self.assertIsNotNone(build)
            self.assertEqual(build["status"], "failed")

    def test_resume_keeps_one_build_and_reuses_checkpoints(self) -> None:
        with TemporaryDirectory() as directory:
            stage_runner = StageRunner(Path(directory) / "work")
            build_id = stage_runner.create_build("armenia")
            stage = _write_stage("extract.txt", "one")
            first = stage_runner.run(
                product="armenia",
                stage=stage.name,
                command=stage.command,
                build_id=build_id,
                expected_outputs=stage.expected_outputs,
            )

            result = PipelineRunner(stage_runner).run(
                product="armenia", stages=(stage,), build_id=build_id
            )

            self.assertEqual(first.status, "success")
            self.assertEqual(result.stages[0].status, "skipped")
            self.assertEqual(result.stages[0].reused_attempt_id, first.attempt_id)


if __name__ == "__main__":
    unittest.main()

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

    def test_finalize_runs_before_success_and_failure_is_terminal(self) -> None:
        with TemporaryDirectory() as directory:
            stage_runner = StageRunner(Path(directory) / "work")
            pipeline = PipelineRunner(stage_runner)
            seen_build_ids: list[str] = []

            successful = pipeline.run(
                product="armenia",
                stages=lambda build_id: (
                    _write_stage("extract.txt", build_id),
                ),
                finalize=lambda build_id: seen_build_ids.append(build_id) or {"published": True},
            )
            self.assertEqual(seen_build_ids, [successful.build_id])
            self.assertEqual(successful.final_result, {"published": True})

            with self.assertRaisesRegex(RuntimeError, "publish failed"):
                pipeline.run(
                    product="belarus",
                    stages=(_write_stage("extract.txt", "ok"),),
                    finalize=lambda _build_id: (_ for _ in ()).throw(
                        RuntimeError("publish failed")
                    ),
                )
            builds = stage_runner.history.latest_success_by_product()
            self.assertIn("armenia", builds)
            self.assertNotIn("belarus", builds)
            self.assertNotIn("belarus", stage_runner.history.running_products())

    def test_declared_directories_exist_before_command(self) -> None:
        with TemporaryDirectory() as directory:
            stage_runner = StageRunner(Path(directory) / "work")
            command = (
                sys.executable,
                "-c",
                "from pathlib import Path; "
                "assert Path('tiles').is_dir(); "
                "Path('tiles/result.txt').write_text('ok', encoding='utf-8')",
            )

            result = PipelineRunner(stage_runner).run(
                product="armenia",
                stages=(
                    PipelineStage(
                        "splitter",
                        command,
                        ("tiles",),
                        ("tiles",),
                    ),
                ),
            )

            self.assertEqual(result.status, "success")


if __name__ == "__main__":
    unittest.main()

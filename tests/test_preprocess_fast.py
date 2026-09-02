from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.preprocess_fast import (
    ANALYSIS_MANIFEST,
    _source_identity,
    _validate_reusable_analysis,
    _write_analysis_manifest,
)


class FastPreprocessReuseTests(unittest.TestCase):
    def _prepare(self, root: Path) -> tuple[Path, Path, dict[str, int]]:
        source = root / "source.osm.pbf"
        source.write_bytes(b"test-pbf")
        analysis = root / "analysis"
        analysis.mkdir()
        (analysis / "road-density.json.gz").write_bytes(b"road")
        (analysis / "poi-context.json.gz").write_bytes(b"poi")
        area_stats = {"created": 7, "candidates": 7}
        _write_analysis_manifest(analysis, source, area_stats)
        return source, analysis, area_stats

    def test_reuse_accepts_exact_source_and_area_state(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, area_stats = self._prepare(root)
            payload = _validate_reusable_analysis(analysis, source, area_stats)
            self.assertEqual(payload["source"], _source_identity(source))
            self.assertTrue((analysis / ANALYSIS_MANIFEST).is_file())

    def test_reuse_rejects_changed_source(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, area_stats = self._prepare(root)
            source.write_bytes(b"changed-pbf-size")
            with self.assertRaises(StageError):
                _validate_reusable_analysis(analysis, source, area_stats)

    def test_reuse_rejects_changed_area_state(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, area_stats = self._prepare(root)
            changed = dict(area_stats)
            changed["created"] += 1
            with self.assertRaises(StageError):
                _validate_reusable_analysis(analysis, source, changed)

    def test_manifest_is_plain_json_for_manual_inspection(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            payload = json.loads((analysis / ANALYSIS_MANIFEST).read_text(encoding="utf-8"))
            self.assertEqual(payload["source"]["path"], str(source.resolve()))


if __name__ == "__main__":
    unittest.main()

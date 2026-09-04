from __future__ import annotations

import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.poi_context_analysis import (
    ANALYSIS_KIND as POI_ANALYSIS_KIND,
    SCHEMA_VERSION as POI_SCHEMA_VERSION,
    save_poi_context_analysis,
)
from uralla_build.preprocess_fast import (
    ANALYSIS_MANIFEST,
    _source_identity,
    _validate_reusable_analysis,
    _write_analysis_manifest,
)
from uralla_build.road_density_analysis import (
    ANALYSIS_KIND as ROAD_ANALYSIS_KIND,
    SCHEMA_VERSION as ROAD_SCHEMA_VERSION,
    save_road_density_analysis,
)


class FastPreprocessReuseTests(unittest.TestCase):
    def _prepare(self, root: Path) -> tuple[Path, Path, dict[str, int]]:
        source = root / "source.osm.pbf"
        source.write_bytes(b"test-pbf")
        analysis = root / "analysis"
        analysis.mkdir()
        save_road_density_analysis(
            analysis / "road-density.json.gz",
            {
                "schema_version": ROAD_SCHEMA_VERSION,
                "kind": ROAD_ANALYSIS_KIND,
                "ways": {},
            },
        )
        save_poi_context_analysis(
            analysis / "poi-context.json.gz",
            {
                "schema_version": POI_SCHEMA_VERSION,
                "kind": POI_ANALYSIS_KIND,
                "nodes": {},
            },
        )
        area_stats = {"created": 7, "candidates": 7}
        area_payload = {
            "schema_version": 3,
            "kind": "area_pois",
            "source": _source_identity(source),
            "stats": area_stats,
            "nodes": [],
            "enrichments": [],
        }
        with gzip.open(analysis / "area-pois.json.gz", "wt", encoding="utf-8") as handle:
            json.dump(area_payload, handle)
        _write_analysis_manifest(analysis, source, area_stats)
        return source, analysis, area_stats

    def test_reuse_accepts_exact_source_and_all_current_artifacts(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            payload = _validate_reusable_analysis(analysis, source)
            self.assertEqual(payload["source"], _source_identity(source))
            self.assertTrue((analysis / ANALYSIS_MANIFEST).is_file())

    def test_reuse_accepts_newer_bytes_for_same_extract_name(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            source.write_bytes(b"changed-pbf-size-and-mtime")
            payload = _validate_reusable_analysis(analysis, source)
            self.assertEqual(payload["source"]["name"], source.name)

    def test_reuse_rejects_different_extract_name(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            other = root / "another-region.osm.pbf"
            other.write_bytes(source.read_bytes())
            with self.assertRaises(StageError):
                _validate_reusable_analysis(analysis, other)

    def test_reuse_rejects_missing_area_artifact(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            (analysis / "area-pois.json.gz").unlink()
            with self.assertRaises(StageError):
                _validate_reusable_analysis(analysis, source)

    def test_reuse_rejects_stale_road_density_schema_before_apply(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            save_road_density_analysis(
                analysis / "road-density.json.gz",
                {
                    "schema_version": ROAD_SCHEMA_VERSION - 1,
                    "kind": ROAD_ANALYSIS_KIND,
                    "ways": {},
                },
            )
            with self.assertRaisesRegex(StageError, "unsupported road-density"):
                _validate_reusable_analysis(analysis, source)

    def test_reuse_rejects_stale_poi_context_schema_before_apply(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            save_poi_context_analysis(
                analysis / "poi-context.json.gz",
                {
                    "schema_version": POI_SCHEMA_VERSION - 1,
                    "kind": POI_ANALYSIS_KIND,
                    "nodes": {},
                },
            )
            with self.assertRaisesRegex(StageError, "unsupported POI-context"):
                _validate_reusable_analysis(analysis, source)

    def test_manifest_is_plain_json_for_manual_inspection(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, analysis, _ = self._prepare(root)
            payload = json.loads((analysis / ANALYSIS_MANIFEST).read_text(encoding="utf-8"))
            self.assertEqual(payload["source"]["path"], str(source.resolve()))
            self.assertEqual(payload["reuse_scope"]["source_name"], source.name)
            self.assertEqual(payload["artifacts"]["area_pois"], "area-pois.json.gz")


if __name__ == "__main__":
    unittest.main()

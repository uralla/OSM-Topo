from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import uralla_build.preprocess_pipeline as pipeline


class PreprocessPipelineTests(unittest.TestCase):
    def test_area_pois_are_created_before_semantic_and_density(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.osm.pbf"
            output = root / "output.osm.pbf"
            report = root / "report.json"
            source.write_bytes(b"")
            order: list[str] = []

            def fake_area(input_path, output_path, osmium, *, reporter=None):
                self.assertEqual(Path(input_path), source)
                order.append("area")
                return {"synthesized": 1}

            def fake_semantic(input_path, output_path, config, profiles, report_path):
                self.assertIn(".area-pois.osm.pbf", str(input_path))
                order.append("semantic")
                Path(report_path).write_text("{}\n", encoding="utf-8")
                return {}

            def fake_density(input_path, output_path, osmium, *, reporter=None):
                self.assertIn(".semantic.osm.pbf", str(input_path))
                order.append("density")
                return {"tagged_ways": 1}

            with (
                patch.object(pipeline, "_load_osmium", return_value=object()),
                patch.object(pipeline, "augment_area_pois", side_effect=fake_area),
                patch.object(pipeline, "preprocess_pbf", side_effect=fake_semantic),
                patch.object(pipeline, "augment_road_density", side_effect=fake_density),
                patch.object(pipeline, "_sort_pbf", side_effect=lambda _path: order.append("sort")),
                patch.object(pipeline, "_renumber_nodes", side_effect=lambda _path: order.append("renumber")),
            ):
                rc = pipeline.run_preprocess_pipeline(
                    [
                        "--input",
                        str(source),
                        "--output",
                        str(output),
                        "--profile",
                        "test",
                        "--report",
                        str(report),
                    ]
                )

            self.assertEqual(rc, 0)
            self.assertEqual(order, ["area", "semantic", "density", "sort", "renumber"])
            saved = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(saved["area_pois"], {"synthesized": 1})
            self.assertEqual(saved["road_density"], {"tagged_ways": 1})


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.road_density_analysis import (
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    load_road_density_analysis,
    save_road_density_analysis,
)


class RoadDensityAnalysisTests(unittest.TestCase):
    def test_road_density_analysis_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "road-density.json.gz"
            payload = {
                "schema_version": SCHEMA_VERSION,
                "kind": ANALYSIS_KIND,
                "source": {"path": "ural-s.osm.pbf"},
                "parameters": {},
                "stats": {"tagged_ways": 2},
                "ways": {
                    "16879369": ["local", "very_dense"],
                    "13796096": ["local", "dense"],
                },
            }

            save_road_density_analysis(path, payload)
            loaded = load_road_density_analysis(path)

            self.assertEqual(loaded, payload)
            self.assertGreater(path.stat().st_size, 0)

    def test_road_density_analysis_rejects_wrong_kind(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrong.json.gz"
            save_road_density_analysis(
                path,
                {
                    "schema_version": SCHEMA_VERSION,
                    "kind": "poi_context",
                    "ways": {},
                },
            )

            with self.assertRaises(StageError):
                load_road_density_analysis(path)


if __name__ == "__main__":
    unittest.main()

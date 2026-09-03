from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.road_density import THRESHOLDS, road_density_class
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
                    "16879369": ["service", "very_dense"],
                    "13796096": ["residential", "dense"],
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

    def test_density_classes_are_concrete_and_independent(self) -> None:
        expected = {
            "minor",
            "unclassified",
            "residential",
            "living_street",
            "service",
            "road",
            "track",
        }
        self.assertEqual(set(THRESHOLDS), expected)
        for highway in expected - {"track"}:
            self.assertEqual(road_density_class({"highway": highway}), highway)

    def test_track_aliases_share_only_track_density(self) -> None:
        for highway in ("track", "unsurfaced", "byway"):
            self.assertEqual(road_density_class({"highway": highway}), "track")

    def test_close_biased_non_roads_are_excluded(self) -> None:
        for highway in ("path", "footway", "cycleway", "bridleway", "pedestrian"):
            self.assertIsNone(road_density_class({"highway": highway}))

    def test_service_density_cannot_classify_living_street(self) -> None:
        self.assertEqual(road_density_class({"highway": "service"}), "service")
        self.assertEqual(
            road_density_class({"highway": "living_street"}), "living_street"
        )
        self.assertNotEqual(
            road_density_class({"highway": "service"}),
            road_density_class({"highway": "living_street"}),
        )


if __name__ == "__main__":
    unittest.main()

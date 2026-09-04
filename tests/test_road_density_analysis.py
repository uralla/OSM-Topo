from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.errors import StageError
from uralla_build.road_density import THRESHOLDS, road_density_class
from uralla_build.road_density_analysis import (
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    _dense_components,
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
                "stats": {"tagged_ways": 3, "kept_ways": 1},
                "ways": {
                    "16879369": ["service", "very_dense"],
                    "13796096": ["residential", "dense"],
                    "13796097": ["residential", "keep"],
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

    def test_schema_v3_rejects_v2_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.json.gz"
            save_road_density_analysis(
                path,
                {
                    "schema_version": 2,
                    "kind": ANALYSIS_KIND,
                    "ways": {},
                },
            )
            with self.assertRaisesRegex(StageError, "unsupported road-density"):
                load_road_density_analysis(path)

    def test_dense_components_connect_diagonals_but_not_other_classes(self) -> None:
        levels = {
            ("service", 10, 10): "dense",
            ("service", 11, 11): "very_dense",
            ("service", 20, 20): "dense",
            ("residential", 11, 11): "dense",
        }
        components = _dense_components(levels)
        self.assertEqual(components[("service", 10, 10)], components[("service", 11, 11)])
        self.assertNotEqual(components[("service", 10, 10)], components[("service", 20, 20)])
        self.assertNotEqual(
            components[("service", 11, 11)], components[("residential", 11, 11)]
        )

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

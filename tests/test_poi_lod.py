from __future__ import annotations

import unittest

from uralla_build.poi_lod import classify_poi_lod, intrinsic_floor_for_poi


class PoiLodClassifierTests(unittest.TestCase):
    def test_common_matrix(self) -> None:
        self.assertEqual(classify_poi_lod(priority="common", activity_context="settlement", screen_pressure="medium"), "L")
        self.assertEqual(classify_poi_lod(priority="common", activity_context="settlement", screen_pressure="low"), "M")
        self.assertEqual(classify_poi_lod(priority="common", activity_context="remote", screen_pressure="medium"), "M")
        self.assertEqual(classify_poi_lod(priority="common", activity_context="remote", screen_pressure="low"), "H")
        self.assertEqual(classify_poi_lod(priority="common", activity_context="urban", screen_pressure="low"), "L")

    def test_sparse_never_falls_below_middle(self) -> None:
        for activity in ("remote", "settlement", "urban"):
            for pressure in ("low", "medium", "high"):
                with self.subTest(activity=activity, pressure=pressure):
                    self.assertIn(
                        classify_poi_lod(priority="sparse", activity_context=activity, screen_pressure=pressure),
                        {"M", "H"},
                    )

        self.assertEqual(classify_poi_lod(priority="sparse", activity_context="settlement", screen_pressure="low"), "H")
        self.assertEqual(classify_poi_lod(priority="sparse", activity_context="remote", screen_pressure="high"), "H")
        self.assertEqual(classify_poi_lod(priority="sparse", activity_context="urban", screen_pressure="low"), "M")

    def test_isolated_is_always_high(self) -> None:
        for activity in ("remote", "settlement", "urban"):
            for pressure in ("low", "medium", "high"):
                with self.subTest(activity=activity, pressure=pressure):
                    self.assertEqual(
                        classify_poi_lod(priority="isolated", activity_context=activity, screen_pressure=pressure),
                        "H",
                    )

    def test_intrinsic_floor_preserves_category_importance(self) -> None:
        self.assertEqual(
            classify_poi_lod(
                priority="common",
                activity_context="urban",
                screen_pressure="high",
                intrinsic_floor="M",
            ),
            "M",
        )
        self.assertEqual(
            classify_poi_lod(
                priority="common",
                activity_context="remote",
                screen_pressure="low",
                intrinsic_floor="M",
            ),
            "H",
        )
        self.assertEqual(
            classify_poi_lod(
                priority="common",
                activity_context="settlement",
                screen_pressure="medium",
                intrinsic_floor="H",
            ),
            "H",
        )

    def test_intrinsic_floor_matches_existing_category_fallbacks(self) -> None:
        self.assertEqual(intrinsic_floor_for_poi({"shop": "supermarket"}), "M")
        self.assertEqual(intrinsic_floor_for_poi({"amenity": "supermarket"}), "M")
        self.assertEqual(intrinsic_floor_for_poi({"shop": "convenience"}), "L")
        self.assertEqual(intrinsic_floor_for_poi({"tourism": "hotel"}), "L")
        self.assertEqual(intrinsic_floor_for_poi({"highway": "bus_stop"}), "L")


if __name__ == "__main__":
    unittest.main()

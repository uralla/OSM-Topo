from __future__ import annotations

import unittest

from uralla_build.poi_context import (
    FoodShopIndex,
    classify_activity_context,
    classify_food_shop,
    is_food_shop,
    is_meaningful_context_node,
)


class PoiContextTests(unittest.TestCase):
    def test_food_shop_detection(self) -> None:
        self.assertTrue(is_food_shop({"shop": "supermarket"}))
        self.assertTrue(is_food_shop({"shop": "convenience"}))
        self.assertTrue(is_food_shop({"amenity": "supermarket"}))
        self.assertFalse(is_food_shop({"shop": "clothes"}))

    def test_meaningful_context_node_detection(self) -> None:
        self.assertFalse(is_meaningful_context_node({}))
        self.assertFalse(is_meaningful_context_node({"source": "survey"}))
        self.assertFalse(is_meaningful_context_node({"fixme": "check"}))
        self.assertTrue(is_meaningful_context_node({"amenity": "toilets"}))
        self.assertTrue(is_meaningful_context_node({"addr:housenumber": "3"}))
        self.assertTrue(is_meaningful_context_node({"natural": "peak"}))

    def test_activity_context_classifier(self) -> None:
        kwargs = dict(local_p25=20, local_p75=100, background_p25=200, background_p75=1000)
        self.assertEqual(classify_activity_context(activity_2km=10, activity_10km=100, **kwargs), "remote")
        self.assertEqual(classify_activity_context(activity_2km=50, activity_10km=150, **kwargs), "settlement")
        self.assertEqual(classify_activity_context(activity_2km=150, activity_10km=1500, **kwargs), "urban")
        self.assertEqual(classify_activity_context(activity_2km=150, activity_10km=100, **kwargs), "settlement")

    def test_rarity_classes(self) -> None:
        self.assertEqual(
            classify_food_shop(shops_2km=1, shops_10km=2),
            ("remote", "isolated"),
        )
        self.assertEqual(
            classify_food_shop(shops_2km=2, shops_10km=7),
            ("settlement", "sparse"),
        )
        self.assertEqual(
            classify_food_shop(shops_2km=8, shops_10km=30),
            ("urban", "common"),
        )


    def test_meaningful_context_node_filter(self) -> None:
        self.assertFalse(is_meaningful_context_node({}))
        self.assertFalse(is_meaningful_context_node({"source": "survey"}))
        self.assertFalse(is_meaningful_context_node({"note": "check later", "fixme": "verify"}))
        self.assertFalse(is_meaningful_context_node({"source:maxspeed": "RU:urban"}))
        self.assertTrue(is_meaningful_context_node({"amenity": "toilets"}))
        self.assertTrue(is_meaningful_context_node({"addr:housenumber": "3"}))
        self.assertTrue(is_meaningful_context_node({"tourism": "guest_house", "source": "survey"}))

    def test_grid_distance_count_10km_background(self) -> None:
        index = FoodShopIndex.empty()
        index.add(55.0000, 60.0000)
        index.add(55.0500, 60.0000)
        index.add(55.1200, 60.0000)
        self.assertEqual(index.count_within(55.0000, 60.0000, 10.0), 2)

    def test_grid_circle_background_count(self) -> None:
        index = FoodShopIndex.empty()
        index.add(55.0000, 60.0000)
        index.add(55.0500, 60.0000)
        index.add(55.1200, 60.0000)
        exact = index.count_within(55.0000, 60.0000, 10.0)
        background = index.count_cells_within_circle(55.0000, 60.0000, 10.0)
        self.assertGreaterEqual(background, exact)
        self.assertEqual(exact, 2)

    def test_grid_distance_count(self) -> None:
        index = FoodShopIndex.empty()
        index.add(55.0000, 60.0000)
        index.add(55.0100, 60.0000)
        index.add(55.1000, 60.0000)
        self.assertEqual(index.count_within(55.0000, 60.0000, 2.0), 2)
        self.assertEqual(index.count_within(55.0000, 60.0000, 12.0), 3)


if __name__ == "__main__":
    unittest.main()

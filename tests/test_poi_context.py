from __future__ import annotations

import unittest

from uralla_build.poi_context import FoodShopIndex, classify_food_shop, is_food_shop


class PoiContextTests(unittest.TestCase):
    def test_food_shop_detection(self) -> None:
        self.assertTrue(is_food_shop({"shop": "supermarket"}))
        self.assertTrue(is_food_shop({"shop": "convenience"}))
        self.assertTrue(is_food_shop({"amenity": "supermarket"}))
        self.assertFalse(is_food_shop({"shop": "clothes"}))

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

    def test_grid_distance_count(self) -> None:
        index = FoodShopIndex.empty()
        index.add(55.0000, 60.0000)
        index.add(55.0100, 60.0000)
        index.add(55.1000, 60.0000)
        self.assertEqual(index.count_within(55.0000, 60.0000, 2.0), 2)
        self.assertEqual(index.count_within(55.0000, 60.0000, 12.0), 3)


if __name__ == "__main__":
    unittest.main()

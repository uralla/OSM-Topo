from __future__ import annotations

import unittest

from uralla_build.poi_context import (
    FoodShopIndex,
    WeightedPointIndex,
    classify_activity_context,
    apply_activity_place_guard,
    classify_food_shop,
    classify_screen_pressure,
    classify_outdoor_rarity,
    is_outdoor_furniture,
    is_tourist_retail,
    is_picnic_site,
    is_food_shop,
    is_meaningful_context_node,
    screen_pressure_weight,
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

    def test_screen_pressure_weights(self) -> None:
        self.assertEqual(screen_pressure_weight({"addr:housenumber": "3"}), 0)
        self.assertEqual(screen_pressure_weight({"amenity": "toilets"}), 1)
        self.assertEqual(screen_pressure_weight({"tourism": "hotel", "name": "Солнышко"}), 2)
        self.assertEqual(screen_pressure_weight({"place": "village", "name": "Тест"}), 4)

    def test_screen_pressure_classifier(self) -> None:
        kwargs = dict(local_p25=20, local_p75=100, background_p25=200, background_p75=1000)
        self.assertEqual(classify_screen_pressure(pressure_2km=10, pressure_10km=100, **kwargs), "low")
        self.assertEqual(classify_screen_pressure(pressure_2km=10, pressure_10km=900, **kwargs), "low")
        self.assertEqual(classify_screen_pressure(pressure_2km=10, pressure_10km=1000, **kwargs), "medium")
        self.assertEqual(classify_screen_pressure(pressure_2km=50, pressure_10km=500, **kwargs), "medium")
        self.assertEqual(classify_screen_pressure(pressure_2km=150, pressure_10km=1500, **kwargs), "high")
        # Ai-Petri control shape: locally below p25, broad background below p75.
        self.assertEqual(
            classify_screen_pressure(
                pressure_2km=131, pressure_10km=6793,
                local_p25=207, local_p75=1343,
                background_p25=2117, background_p75=7735,
            ),
            "low",
        )

    def test_weighted_screen_pressure_index(self) -> None:
        index = WeightedPointIndex.empty()
        index.add(55.0000, 60.0000, 2)
        index.add(55.0100, 60.0000, 4)
        index.add(55.1000, 60.0000, 10)
        self.assertEqual(index.score_within(55.0000, 60.0000, 2.0), 6)

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


    def test_activity_place_guard_promotes_remote_near_village(self):
        self.assertEqual(
            apply_activity_place_guard(
                "remote", {"village": {"distance_km": 1.89, "name": "Изюмовка"}}
            ),
            "settlement",
        )

    def test_activity_place_guard_keeps_remote_beyond_radius(self):
        self.assertEqual(
            apply_activity_place_guard(
                "remote", {"village": {"distance_km": 2.01, "name": "Далеко"}}
            ),
            "remote",
        )

    def test_activity_place_guard_does_not_change_urban(self):
        self.assertEqual(
            apply_activity_place_guard(
                "urban", {"village": {"distance_km": 0.1, "name": "Рядом"}}
            ),
            "urban",
        )
    def test_outdoor_candidate_detection(self):
        self.assertTrue(is_picnic_site({"tourism": "picnic_site"}))
        self.assertTrue(is_outdoor_furniture({"amenity": "bench"}))
        self.assertTrue(is_outdoor_furniture({"leisure": "picnic_table"}))
        self.assertFalse(is_outdoor_furniture({"amenity": "shelter"}))

    def test_outdoor_rarity(self):
        self.assertEqual(classify_outdoor_rarity(objects_2km=1, objects_10km=10), ("remote", "isolated"))
        self.assertEqual(classify_outdoor_rarity(objects_2km=3, objects_10km=25), ("settlement", "sparse"))
        self.assertEqual(classify_outdoor_rarity(objects_2km=4, objects_10km=26), ("urban", "common"))


if __name__ == "__main__":
    unittest.main()


def test_tourist_retail_whitelist_is_adaptive():
    for value in ("bicycle", "hardware", "doityourself", "houseware", "sports", "outdoor"):
        assert is_tourist_retail({"shop": value})
    for value in ("books", "mobile_phone", "medical_supply"):
        assert not is_tourist_retail({"shop": value})

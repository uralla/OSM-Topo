from uralla_build.area_pois import (
    area_poi_equivalent_kinds,
    area_poi_kind,
    interior_point,
    point_in_polygon,
)


def test_interior_point_stays_inside_l_shaped_polygon():
    ring = [
        (0.0, 0.0),
        (4.0, 0.0),
        (4.0, 1.0),
        (1.0, 1.0),
        (1.0, 4.0),
        (0.0, 4.0),
        (0.0, 0.0),
    ]
    point = interior_point(ring)
    assert point is not None
    assert point_in_polygon(point, ring)
    # The bounding-box centre (2,2) is outside this L shape; our point must not be it.
    assert point != (2.0, 2.0)


def test_point_in_polygon_rejects_l_shape_hole_like_corner():
    ring = [
        (0.0, 0.0),
        (4.0, 0.0),
        (4.0, 1.0),
        (1.0, 1.0),
        (1.0, 4.0),
        (0.0, 4.0),
        (0.0, 0.0),
    ]
    assert point_in_polygon((0.5, 3.0), ring)
    assert not point_in_polygon((2.0, 2.0), ring)


def test_common_facility_areas_become_pois():
    assert area_poi_kind({"amenity": "marketplace"}) == "amenity:marketplace"
    assert area_poi_kind({"tourism": "hotel"}) == "tourism:hotel"
    assert area_poi_kind({"amenity": "school"}) == "amenity:school"
    assert area_poi_kind({"shop": "supermarket"}) == "shop:supermarket"
    assert area_poi_kind({"amenity": "fuel", "shop": "convenience"}) == "amenity:fuel"


def test_multi_tag_real_castle_covers_historic_and_tourism_kinds():
    tags = {
        "historic": "castle",
        "castle_type": "fortress",
        "tourism": "attraction",
        "name": "Мангуп Кале",
    }
    assert area_poi_kind(tags) == "tourism:attraction"
    assert area_poi_equivalent_kinds(tags) == (
        "tourism:attraction",
        "historic:castle",
    )


def test_named_area_point_rules_keep_their_name_requirement():
    assert area_poi_kind({"leisure": "park"}) is None
    assert area_poi_kind({"leisure": "park", "name": "Парк"}) == "leisure:park"
    assert area_poi_kind({"landuse": "forest"}) is None
    assert area_poi_kind({"landuse": "forest", "name": "Бор"}) == "landuse:forest"


def test_area_only_geography_does_not_get_synthetic_centre_poi():
    assert area_poi_kind({"natural": "water", "name": "Озеро"}) is None
    assert area_poi_kind({"natural": "wetland", "name": "Болото"}) is None
    assert area_poi_kind({"natural": "glacier", "name": "Ледник"}) is None
    assert area_poi_kind({"boundary": "protected_area", "name": "Заказник"}) is None
    assert area_poi_kind({"leisure": "nature_reserve", "name": "Заповедник"}) is None


def test_intentionally_hidden_point_categories_stay_hidden_for_areas():
    assert area_poi_kind({"leisure": "playground"}) is None
    assert area_poi_kind({"leisure": "sports_centre"}) is None
    assert area_poi_kind({"leisure": "swimming_pool"}) is None


def test_kite_areas_are_eligible_across_inconsistent_tagging():
    assert area_poi_kind({"sport": "kitesurfing"}) == "kite:infrastructure"
    assert area_poi_kind({"brand": "Кайтшкола номер один"}) == "kite:infrastructure"
    assert area_poi_kind({"designation": "Kitesurfing"}) == "kite:infrastructure"
    assert area_poi_kind({"name": 'Школа кайтсерфинга "Точка отрыва"'}) == "kite:infrastructure"
    assert area_poi_kind({"description": "Кайт станция и прокат оборудования"}) == "kite:infrastructure"

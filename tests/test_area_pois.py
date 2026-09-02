from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.area_pois import (
    area_poi_equivalent_kinds,
    area_poi_kind,
    area_poi_merge_families,
    discover_area_poi_plan,
    write_area_pois,
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


class AreaPoiMergeTests(unittest.TestCase):
    def _plan(
        self,
        *,
        area_tags: dict[str, str],
        poi_nodes: list[tuple[int, float, float, dict[str, str]]],
    ):
        try:
            import osmium
        except ImportError:
            self.skipTest("optional osmium dependency is not installed")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "input.osm"
            node_xml = []
            for node_id, lon, lat, tags in poi_nodes:
                rendered_tags = "".join(
                    f"<tag k='{key}' v='{value}'/>" for key, value in tags.items()
                )
                node_xml.append(
                    f"<node id='{node_id}' lat='{lat}' lon='{lon}' version='1'>"
                    f"{rendered_tags}</node>"
                )
            area_xml = "".join(
                f"<tag k='{key}' v='{value}'/>" for key, value in area_tags.items()
            )
            source.write_text(
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<osm version='0.6' generator='uralla-test'>"
                "<node id='1' lat='55.0000' lon='37.0000' version='1'/>"
                "<node id='2' lat='55.0000' lon='37.0010' version='1'/>"
                "<node id='3' lat='55.0010' lon='37.0010' version='1'/>"
                "<node id='4' lat='55.0010' lon='37.0000' version='1'/>"
                + "".join(node_xml)
                + "<way id='100' version='3'>"
                "<nd ref='1'/><nd ref='2'/><nd ref='3'/><nd ref='4'/><nd ref='1'/>"
                + area_xml
                + "</way></osm>",
                encoding="utf-8",
            )
            return discover_area_poi_plan(str(source), osmium), osmium, source.read_text(encoding="utf-8")

    def test_accommodation_area_enriches_existing_different_accommodation_type(self):
        plan, _osmium, _source = self._plan(
            area_tags={
                "building": "yes",
                "tourism": "guest_house",
                "name": 'Приют "Байсакал"',
                "website": "https://vk.com/iremel_tourism",
            },
            poi_nodes=[(10, 37.0005, 55.0005, {"tourism": "hostel"})],
        )
        self.assertFalse(plan.synthetic)
        self.assertFalse(plan.ambiguous)
        self.assertEqual(len(plan.enrichments), 1)
        enrichment = plan.enrichments[0]
        self.assertEqual(enrichment.family, "accommodation")
        self.assertEqual(enrichment.node_kind, "tourism:hostel")
        self.assertEqual(
            enrichment.added_tags,
            {
                "name": 'Приют "Байсакал"',
                "website": "https://vk.com/iremel_tourism",
            },
        )

    def test_retail_area_enriches_the_only_compatible_shop_node(self):
        plan, _osmium, _source = self._plan(
            area_tags={
                "building": "retail",
                "shop": "convenience",
                "name": "Магнит",
                "opening_hours": "08:00-22:00",
            },
            poi_nodes=[(10, 37.0005, 55.0005, {"shop": "supermarket"})],
        )
        self.assertFalse(plan.synthetic)
        self.assertEqual(plan.enrichments[0].family, "retail")
        self.assertEqual(
            plan.enrichments[0].added_tags,
            {"name": "Магнит", "opening_hours": "08:00-22:00"},
        )

    def test_legacy_amenity_supermarket_matches_shop_without_copying_its_type(self):
        plan, _osmium, _source = self._plan(
            area_tags={"amenity": "supermarket", "name": "Магазин"},
            poi_nodes=[(10, 37.0005, 55.0005, {"shop": "convenience"})],
        )
        self.assertFalse(plan.synthetic)
        self.assertEqual(plan.enrichments[0].family, "retail")
        self.assertEqual(plan.enrichments[0].added_tags, {"name": "Магазин"})

    def test_multiple_compatible_shop_nodes_are_ambiguous_and_skip_synthetic(self):
        plan, _osmium, _source = self._plan(
            area_tags={"shop": "supermarket"},
            poi_nodes=[
                (10, 37.0003, 55.0005, {"shop": "supermarket"}),
                (11, 37.0007, 55.0005, {"shop": "convenience"}),
            ],
        )
        self.assertFalse(plan.synthetic)
        self.assertFalse(plan.enrichments)
        self.assertEqual(plan.ambiguous[0].node_ids, (10, 11))

    def test_bank_does_not_merge_with_atm_and_fuel_does_not_merge_with_shop(self):
        bank, _osmium, _source = self._plan(
            area_tags={"amenity": "bank", "name": "Банк"},
            poi_nodes=[(10, 37.0005, 55.0005, {"amenity": "atm"})],
        )
        fuel, _osmium, _source = self._plan(
            area_tags={"amenity": "fuel", "shop": "convenience", "name": "АЗС"},
            poi_nodes=[(10, 37.0005, 55.0005, {"shop": "convenience"})],
        )
        self.assertEqual(bank.synthetic[0].kind, "amenity:bank")
        self.assertEqual(fuel.synthetic[0].kind, "amenity:fuel")

    def test_near_boundary_match_uses_small_metric_tolerance(self):
        plan, _osmium, _source = self._plan(
            area_tags={"shop": "supermarket", "name": "Магазин"},
            poi_nodes=[
                (10, 37.00105, 55.0005, {"shop": "convenience", "name": "Магазин"})
            ],
        )
        self.assertFalse(plan.synthetic)
        self.assertEqual(plan.enrichments[0].match, "near")
        self.assertLessEqual(plan.enrichments[0].distance_metres, 8.0)

    def test_write_preserves_node_type_and_adds_area_information(self):
        plan, osmium, source_xml = self._plan(
            area_tags={
                "building": "yes",
                "tourism": "guest_house",
                "name": 'Приют "Байсакал"',
                "website": "https://vk.com/iremel_tourism",
            },
            poi_nodes=[(10, 37.0005, 55.0005, {"tourism": "hostel"})],
        )
        with TemporaryDirectory() as directory:
            source = Path(directory) / "input.osm"
            source.write_text(source_xml, encoding="utf-8")
            output = Path(directory) / "output.osm.pbf"
            stats = write_area_pois(
                source,
                output,
                plan.synthetic,
                osmium,
                enrichments=plan.enrichments,
                ambiguous=plan.ambiguous,
            )
            nodes = {
                int(item.id): dict(item.tags)
                for item in osmium.FileProcessor(str(output))
                if item.type_str() == "n"
            }
        self.assertEqual(nodes[10]["tourism"], "hostel")
        self.assertEqual(nodes[10]["name"], 'Приют "Байсакал"')
        self.assertEqual(nodes[10]["website"], "https://vk.com/iremel_tourism")
        self.assertEqual(stats["enriched_nodes"], 1)

    def test_family_mapping_is_intentionally_strict_outside_safe_groups(self):
        self.assertEqual(area_poi_merge_families({"tourism": "hostel"}), ("accommodation",))
        self.assertEqual(area_poi_merge_families({"shop": "general"}), ("retail",))
        self.assertEqual(
            area_poi_merge_families({"healthcare": "clinic"}),
            ("medical:clinic_doctors",),
        )
        self.assertEqual(area_poi_merge_families({"amenity": "bank"}), ("amenity:bank",))
        self.assertEqual(area_poi_merge_families({"amenity": "atm"}), ())

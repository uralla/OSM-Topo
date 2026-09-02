from pathlib import Path
import re
import unittest

from uralla_build.area_pois import area_poi_kind


ROOT = Path(__file__).resolve().parents[1]
POLYGONS = ROOT / "styles/uralla/polygons"
LANDUSE = ROOT / "styles/uralla/inc/landuse_polygons"
WATER = ROOT / "styles/uralla/inc/water_polygons"
TYP = ROOT / "styles/uralla.txt"


class PolygonAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.polygons = POLYGONS.read_text(encoding="utf-8")
        cls.landuse = LANDUSE.read_text(encoding="utf-8")
        cls.water = WATER.read_text(encoding="utf-8")
        cls.typ = TYP.read_text(encoding="utf-8")

    def test_building_no_is_not_rendered_as_a_building(self) -> None:
        self.assertIn("building=* & building!=no & building!=ruins", self.polygons)

    def test_city_and_town_match_their_typ_semantics(self) -> None:
        self.assertIn("place=city & building!=* [0x01 resolution 18]", self.polygons)
        self.assertIn("place=town & building!=* [0x02 resolution 19]", self.polygons)

    def test_fuel_precedes_shop_without_rewriting_highway(self) -> None:
        fuel = "amenity=fuel & building!=* [0x10f0c resolution 24]"
        shop = "shop=* & building!=* [0x08 resolution 21]"
        self.assertLess(self.polygons.index(fuel), self.polygons.index(shop))
        self.assertNotIn("delete highway", self.polygons)
        self.assertNotIn("set highway=rest_area", self.polygons)

    def test_generic_man_made_fallback_is_late_and_non_destructive(self) -> None:
        fallback = "man_made=* & area!=no"
        self.assertGreater(self.polygons.index(fallback), self.polygons.index("historic=archaeological_site"))
        self.assertNotIn("man_made=* & landuse=* {delete man_made}", self.polygons)
        self.assertNotIn("man_made=* & natural=* {delete man_made}", self.polygons)

    def test_waterfall_is_point_only(self) -> None:
        self.assertNotRegex(self.water, r"waterfall[^\n]*\[0x")

    def test_basin_requires_explicit_water_semantics(self) -> None:
        self.assertNotIn("waterway=riverbank & mkgmap:area2poi!=true | landuse=basin", self.water)
        self.assertIn("landuse=basin & water=*", self.water)

    def test_geoglyph_does_not_reuse_forest_polygon(self) -> None:
        self.assertNotRegex(self.polygons, r"man_made=geoglyph[^\n]*\[0x")
        self.assertIn("man_made!=geoglyph", self.polygons)
        self.assertEqual(
            area_poi_kind({"man_made": "geoglyph", "name": "Геоглиф"}),
            "man_made:geoglyph",
        )

    def test_military_airfield_keeps_base_and_overlay(self) -> None:
        self.assertIn("military=airfield [0x07 resolution 18 continue]", self.landuse)

    def test_leaf_type_only_classifies_wood(self) -> None:
        for rule in (
            "natural=wood & leaf_type=needleleaved",
            "natural=wood & leaf_type=broadleaved",
            "natural=wood & wood=coniferous",
            "natural=wood & wood=deciduous",
        ):
            self.assertIn(rule, self.landuse)
        self.assertNotRegex(self.landuse, r"(?m)^leaf_type=.*\[")
        self.assertNotRegex(self.landuse, r"(?m)^wood=.*\[")

    def test_native_polygon_types_are_in_draw_order(self) -> None:
        draw_order = self.typ[self.typ.index("[_drawOrder]"):self.typ.index("[end]", self.typ.index("[_drawOrder]"))]
        self.assertIn("Type=0x00e,7", draw_order)
        self.assertNotIn("Type=0x01e,", draw_order)

    def test_road_areas_have_truthful_custom_types(self) -> None:
        self.assertIn("highway=rest_area & (area=yes | mkgmap:mp_created=true)", self.polygons)
        self.assertIn("[0x10f15 resolution 21]", self.polygons)
        self.assertIn("highway=living_street | highway=residential | highway=unclassified", self.polygons)
        self.assertIn("[0x10f16 resolution 21]", self.polygons)
        self.assertIn("String1=0x19,зона отдыха", self.typ)
        self.assertIn("String1=0x19,дорожная зона", self.typ)

    def test_only_archaeological_sites_keep_a_historic_area(self) -> None:
        self.assertNotIn("historic=museum | historic=memorial [", self.polygons)
        self.assertIn("historic=archaeological_site", self.polygons)
        self.assertIn("[0x10f17 resolution 21]", self.polygons)
        self.assertIn("String1=0x19,археологический объект", self.typ)
        self.assertEqual(
            area_poi_kind({"historic": "memorial", "name": "Мемориал"}),
            "historic:memorial",
        )

    def test_prison_and_bridge_have_dedicated_types(self) -> None:
        self.assertIn("amenity=prison & building!=*", self.polygons)
        self.assertIn("[0x10f18 resolution 22]", self.polygons)
        self.assertIn("bridge=yes & area=yes", self.polygons)
        self.assertIn("[0x10f19 resolution 24]", self.polygons)
        self.assertLess(
            self.polygons.index("bridge=yes & area=yes"),
            self.polygons.index("building=* & building!=no"),
        )
        self.assertIn("String1=0x19,тюрьма", self.typ)
        self.assertIn("String1=0x19,мост", self.typ)

    def test_retired_reservation_polygon_is_absent(self) -> None:
        polygon_sections = re.findall(r"(?ims)^\[_polygon\].*?^\[end\]", self.typ)
        self.assertFalse(any(re.search(r"(?im)^Type=0x0d$", section) for section in polygon_sections))
        self.assertNotIn("Type=0x00d,", self.typ)

    def test_military_area_has_neutral_semantics(self) -> None:
        self.assertIn("String1=0x19,военная территория", self.typ)
        self.assertIn("String2=0x04,military area", self.typ)
        self.assertNotIn("String1=0x19,запретная зона", self.typ)


if __name__ == "__main__":
    unittest.main()

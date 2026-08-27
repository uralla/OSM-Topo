from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / 'styles' / 'uralla'
LINES = STYLE / 'lines'
WATER_LINES = STYLE / 'inc' / 'water_lines'


class LineFallbackCleanupTests(unittest.TestCase):
    def test_pier_is_owned_only_by_water_lines(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        water = WATER_LINES.read_text(encoding='utf-8')
        self.assertNotIn("man_made=pier { name 'пирс' } [0x10f07", lines)
        self.assertIn("man_made=pier & is_closed()=false", water)
        self.assertIn("[0x10f07 resolution 24 continue]", water)

    def test_active_narrow_gauge_is_owned_by_early_rule(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        water = WATER_LINES.read_text(encoding='utf-8')
        self.assertIn(
            "railway=narrow_gauge & disused!=yes & abandoned!=yes",
            water,
        )
        self.assertNotIn(
            "railway=narrow_gauge { name '${name} (ужд)' | 'ужд' }",
            lines,
        )

    def test_disused_and_abandoned_narrow_gauge_keep_specific_label(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "railway=narrow_gauge & (disused=yes | abandoned=yes) { name '${name} (недейств. ужд)' | 'недейств. ужд' }",
            lines,
        )
        self.assertIn("railway=* & abandoned=yes [0x1011a resolution 23-24]", lines)

    def test_cable_car_comment_matches_actual_type(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        water = WATER_LINES.read_text(encoding='utf-8')
        self.assertIn('uses the non-routable aerialway type 0x10f15', lines)
        self.assertIn('aerialway=cable_car', water)
        self.assertIn('[0x10f15 resolution 22]', water)

    def test_pipeline_reaches_its_dedicated_farther_lod_rule(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn("man_made!=pipeline & man_made ~ '.*pipe.*'", lines)
        self.assertIn(
            "man_made=pipeline {name '${name}' | '${operator}'} [0x28 resolution 22]",
            lines,
        )

    def test_construction_highway_is_owned_by_construction_rule(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "highway=construction [0x10f19 resolution 22]",
            lines,
        )
        self.assertIn(
            "highway!=construction & highway=* & construction=* [0x10f19 resolution 22 continue]",
            lines,
        )
        self.assertIn(
            "highway!=construction & highway=* & construction=* & maxspeed!=*\n{ add mkgmap:road-speed = '-1' }",
            lines,
        )
        self.assertNotIn(
            "highway=construction | highway=* & construction=* [0x10f19 resolution 22 continue]",
            lines,
        )

    def test_disused_highways_are_non_routable_bad_track_landmarks(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "(disused:highway=* | abandoned:highway=* | highway=disused | highway=abandoned)",
            lines,
        )
        self.assertIn("'плохая грунтовка/неисп'", lines)
        self.assertIn("[0x1001a resolution 24]", lines)
        self.assertIn("highway=* & (disused=yes | abandoned=yes)", lines)
        self.assertNotIn(
            "highway=* & disused=yes [0x12 road_class=0 road_speed=1 resolution 22 continue]",
            lines,
        )
        self.assertNotIn(
            "highway=* & disused=yes & maxspeed!=* { add mkgmap:road-speed = '-2' }",
            lines,
        )

    def test_disused_lifecycle_precedes_active_highway_overlays(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        lifecycle = lines.index(
            "(disused:highway=* | abandoned:highway=* | highway=disused | highway=abandoned)"
        )
        for active in (
            "Smoothness overlay is only for machine-drivable roads",
            "highway=* & oneway=yes & highway!=construction",
            "# зимники и ледовые переправы",
            "# линии мостов дополнительно к дорогам",
        ):
            self.assertLess(lifecycle, lines.index(active))

    def test_protected_area_boundaries_do_not_preempt_highways(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        water = WATER_LINES.read_text(encoding='utf-8')
        rule = "(boundary=protected_area | boundary=national_park) { name '${name}' } [0x12d1b resolution 23]"
        self.assertNotIn(rule, water)
        self.assertIn(rule, lines)
        self.assertGreater(lines.index(rule), lines.index('highway=track & tracktype!=grade1 [0x13 road_class=0 road_speed=1 resolution 24]'))

    def test_ridge_lod_is_non_overlapping_and_unnamed_is_close_zoom_only(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "natural=ridge & name=* & length()>500 { name 'хр. ${name}' } [0x10e02 resolution 18-22 continue]",
            lines,
        )
        self.assertIn(
            "natural=ridge & name=* { name 'хр. ${name}' } [0x10e01 resolution 23-24]",
            lines,
        )
        self.assertIn(
            "natural=ridge & name!=* [0x10e01 resolution 24]",
            lines,
        )
        self.assertNotIn("natural=ridge & name=* & length()>500 { name 'хр. ${name}' } [0x10e02 resolution 18 continue]", lines)
        self.assertNotIn("natural=ridge & name=* { name 'хр. ${name}' } [0x10e01 resolution 23 continue]", lines)
        self.assertNotIn("natural=ridge & name!=* & length()>500", lines)
        self.assertNotIn("natural=ridge & name!=* [0x10e01 resolution 23", lines)

    def test_marked_trails_shift_far_and_near_one_level(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        for rule in (
            "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x07 resolution 21-22 continue]",
            "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x0e road_class=0 road_speed=1 resolution 23-24]",
            "mkgmap:trail_name=* & bicycle=yes & highway=path & length()>100 [0x0b resolution 21-22 continue]",
            "mkgmap:trail_name=* & bicycle=yes & highway=path & length()>100 [0x16 road_class=0 road_speed=1 resolution 23-24]",
            "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x0b resolution 22-22 continue]",
            "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x16 road_class=0 road_speed=0 resolution 23-24]",
            "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x12 resolution 21-22 continue]",
            "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x13 road_class=0 road_speed=1 resolution 23-24]",
            "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x07 resolution 20-22 continue]",
            "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x0a road_class=0 road_speed=1 resolution 23-24]",
            "mkgmap:trail_name=* & highway=bridleway & length()>100 [0x0b resolution 22-22 continue]",
            "mkgmap:trail_name=* & highway=bridleway & length()>100 [0x16 road_class=0 road_speed=0 resolution 23-24]",
        ):
            self.assertIn(rule, lines)
        self.assertNotRegex(lines, r"mkgmap:trail_name=.*resolution 1[0-9]")

    def test_canonical_road_and_trail_near_types_are_routable(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn("highway=track & tracktype=grade1 [0x0a road_class=0 road_speed=1 resolution 24]", lines)
        self.assertIn("highway=track & tracktype!=grade1 [0x13 road_class=0 road_speed=1 resolution 24]", lines)
        self.assertIn("bicycle=yes & highway=path [0x16 road_class=0 road_speed=1 resolution 24]", lines)
        self.assertIn("bicycle!=yes & highway=path [0x16 road_class=0 road_speed=0 resolution 24]", lines)
        self.assertNotIn("0x13504", lines)
        self.assertNotIn("bicycle!=yes & highway=path [0x2e", lines)

    def test_bridleway_uses_ordinary_trail_far_near_hierarchy(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn("highway=bridleway & length()>100 [0x0b resolution 23-23 continue]", lines)
        self.assertIn("highway=bridleway [0x16 road_class=0 road_speed=0 resolution 24]", lines)

    def test_legacy_byway_is_normalized_to_track(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        rule = "highway=byway { set highway=track }"
        self.assertIn(rule, lines)
        self.assertLess(lines.index(rule), lines.index("### taxi type is used for river routing"))
        self.assertNotIn("highway=byway [0x16 road_class=0 road_speed=0 resolution 24]", lines)

    def test_steps_keep_stair_overlay_on_solid_routable_carrier(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        overlay = "highway=steps [0x12d1f resolution 24 continue]"
        carrier = "highway=steps [0x07 road_class=0 road_speed=0 resolution 24]"
        self.assertIn(overlay, lines)
        self.assertIn(carrier, lines)
        self.assertNotIn("highway=steps [0x16 road_class=0 road_speed=0 resolution 24]", lines)
        self.assertLess(lines.index(overlay), lines.index(carrier))

    def test_via_ferrata_uses_its_native_mpc_type(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn("highway=via_ferrata [0x2e resolution 24]", lines)
        self.assertLess(
            lines.index("highway=via_ferrata [0x2e resolution 24]"),
            lines.index("# Mop up any unrecognised highway types"),
        )

    def test_footway_sidewalk_and_trail_semantics_are_separate(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "highway=footway & (footway=sidewalk | footway=crossing) & length()>100 [0x07 resolution 22-23 continue]",
            lines,
        )
        self.assertIn(
            "highway=footway & (footway=sidewalk | footway=crossing) [0x0e road_class=0 road_speed=0 resolution 24]",
            lines,
        )
        self.assertIn(
            "highway=footway & footway!=sidewalk & footway!=crossing & length()>100 [0x0b resolution 23-23 continue]",
            lines,
        )
        self.assertIn(
            "highway=footway & footway!=sidewalk & footway!=crossing [0x16 road_class=0 road_speed=0 resolution 24]",
            lines,
        )
        self.assertNotIn("footway=sidewalk & highway=steps", lines)
        self.assertIn("highway=steps [0x12d1f resolution 24 continue]", lines)

    def test_footway_is_not_duplicated_by_bicycle_path_rule(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "bicycle=yes & highway=path & length()>100 [0x0b resolution 22-23 continue]",
            lines,
        )
        self.assertIn(
            "highway=footway & footway!=sidewalk & footway!=crossing & length()>100 [0x0b resolution 23-23 continue]",
            lines,
        )
        self.assertNotIn(
            "bicycle=yes & highway=path & length()>100 | highway=footway & length()>100",
            lines,
        )

    def test_service_specializations_keep_far_near_hierarchy(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        for rule in (
            "highway=service & (service=alley|service=driveway) [0x07 resolution 23-23 continue]",
            "highway=service & (service=alley|service=driveway) [0x0d road_class=0 road_speed=0 resolution 24]",
            "highway=service & oneway=yes [0x07 resolution 23-23 continue]",
            "highway=service & oneway=yes [0x0d road_class=0 road_speed=1 resolution 24]",
            "highway=service & length()>200 [0x07 resolution 23-23 continue]",
            "highway=service [0x0d road_class=0 road_speed=2 resolution 24]",
        ):
            self.assertIn(rule, lines)
        self.assertNotIn(
            "highway=service & (service=alley|service=driveway) [0x07 road_class=0 road_speed=0 resolution 23]",
            lines,
        )
        self.assertNotIn(
            "highway=service & oneway=yes [0x07 road_class=0 road_speed=1 resolution 23]",
            lines,
        )

    def test_unknown_highway_road_uses_conservative_generic_fallback(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        helper = "highway=road { add mkgmap:dead-end-check = false }"
        fallback = "highway=* & area!=yes & highway!=path & highway!=steps & highway!=footway & highway!=track & highway!=cycleway & highway!=service [0x07 road_class=0 road_speed=0 resolution 24]"
        self.assertIn(helper, lines)
        self.assertIn(fallback, lines)
        self.assertLess(lines.index(helper), lines.index(fallback))
        self.assertNotIn("highway=road { add mkgmap:dead-end-check = false} [0x05 road_class=0 road_speed=1 resolution 21]", lines)
        self.assertNotRegex(lines, r"highway=road .*\[0x[0-9a-fA-F]+ .*resolution")

    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn("power=line & length()>500 [0x29 resolution 21-23 continue]", lines)
        self.assertIn("power=line | power=minor_line [0x29 resolution 24]", lines)
        self.assertNotIn("power=line & man_made=cutline & length()>500", lines)
        self.assertNotIn("power=line | (power=line & man_made=cutline)", lines)

    def test_unclassified_roundabout_uses_only_specialized_resolution_22_rule(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "highway=unclassified & junction!=roundabout [0x06 road_class=1 road_speed=4 resolution 22 continue]",
            lines,
        )
        self.assertIn(
            "highway=unclassified & junction=roundabout [0x06 road_class=1 road_speed=2 resolution 22]",
            lines,
        )
        self.assertNotIn(
            "highway=unclassified [0x06 road_class=1 road_speed=4 resolution 22 continue]",
            lines,
        )


if __name__ == '__main__':
    unittest.main()

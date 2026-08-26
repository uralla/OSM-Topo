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

    def test_unnamed_ridges_keep_lines_without_synthetic_label(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "natural=ridge & name=* & length()>500 { name 'хр. ${name}' }",
            lines,
        )
        self.assertIn(
            "natural=ridge & name!=* & length()>500 [0x10e02 resolution 18 continue]",
            lines,
        )
        self.assertIn(
            "natural=ridge & name!=* [0x10e01 resolution 23 continue]",
            lines,
        )
        self.assertNotIn("natural=ridge { name 'хр. ${name}' }", lines)

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

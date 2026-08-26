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


if __name__ == '__main__':
    unittest.main()

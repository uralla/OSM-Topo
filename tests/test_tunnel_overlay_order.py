from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / 'styles' / 'uralla' / 'lines'


class TunnelOverlayOrderTests(unittest.TestCase):
    def test_railway_tunnel_overlay_runs_after_filters(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        overlay = "railway=* & tunnel=yes & !(railway=light_rail & layer<0) [0x10e04 resolution 24 continue]"
        proposed = "highway=proposed | railway=proposed | bridge=proposed | proposed=*"
        removed = "(highway=razed | highway=dismantled) {deletealltags}"

        self.assertIn("{delete highway; delete railway; delete bridge}", lines)
        self.assertIn(overlay, lines)
        self.assertGreater(lines.index(overlay), lines.index(proposed))
        self.assertGreater(lines.index(overlay), lines.index(removed))
        self.assertLess(lines.index(overlay), lines.index('highway=motorway      { add oneway=yes;'))

    def test_highway_tunnels_run_after_modifiers_and_before_road_types(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        include = "include 'inc/tunnels';"
        road_speed_modifier = "highway=* & mkgmap:unpaved!=1 & smoothness ~ '.*(bad|horrible|impassable)'"
        construction_modifier = "highway!=construction & highway=* & construction=* & maxspeed!=*"
        first_ordinary_road = "highway=primary_link & length()>500"

        self.assertIn(include, lines)
        self.assertGreater(lines.index(include), lines.index(road_speed_modifier))
        self.assertGreater(lines.index(include), lines.index(construction_modifier))
        self.assertLess(lines.index(include), lines.index(first_ordinary_road))

    def test_old_highway_tunnel_overlay_and_fallback_are_gone(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertNotIn(
            "highway=* & tunnel=yes | railway=* & tunnel=yes",
            lines,
        )
        self.assertNotIn("highway=* & tunnel=yes { add name='туннель' }", lines)


if __name__ == '__main__':
    unittest.main()

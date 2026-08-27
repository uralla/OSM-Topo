from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / 'styles' / 'uralla' / 'lines'


class TunnelOverlayOrderTests(unittest.TestCase):
    def test_tunnel_overlay_runs_after_filters(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        overlay = "highway=* & tunnel=yes | railway=* & tunnel=yes & !(railway=light_rail & layer<0) [0x10e04 resolution 24 continue]"
        proposed = "highway=proposed | railway=proposed | bridge=proposed | proposed=*"
        removed = "(highway=razed | highway=dismantled) {deletealltags}"
        inaccessible = "highway=* & tunnel=yes & (access=private|access=no)"

        self.assertIn("{delete highway; delete railway; delete bridge}", lines)
        self.assertIn(overlay, lines)
        self.assertGreater(lines.index(overlay), lines.index(proposed))
        self.assertGreater(lines.index(overlay), lines.index(removed))
        self.assertGreater(lines.index(overlay), lines.index(inaccessible))
        self.assertLess(lines.index(overlay), lines.index('highway=motorway      { add oneway=yes;'))


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ROOT / 'styles' / 'uralla' / 'inc' / 'priority_points'


class InformationPointStyleTests(unittest.TestCase):
    def test_information_fallbacks_exclude_operator_and_ref(self) -> None:
        points = PRIORITY.read_text(encoding='utf-8')
        guidepost = "tourism=information & information=guidepost { name '${name}' | 'указатель' } [0x4c00 resolution 23]"
        route_marker = "tourism=information & (information=route_marker | information=trail_blaze) { name '${name}' | 'маркер' } [0x4c00 resolution 24]"
        generic = "tourism=information { name '${name}' | 'информация' } [0x4c00 resolution 24]"

        self.assertIn(guidepost, points)
        self.assertIn(route_marker, points)
        self.assertIn(generic, points)
        self.assertLess(points.index(guidepost), points.index(generic))
        self.assertLess(points.index(route_marker), points.index(generic))

        information_block = points[points.index(guidepost):points.index(generic) + len(generic)]
        self.assertNotIn("${operator}", information_block)
        self.assertNotIn("${ref}", information_block)


if __name__ == '__main__':
    unittest.main()

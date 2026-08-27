from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'

class InformationPointStyleTests(unittest.TestCase):
    def test_guideposts_are_prioritized_over_generic_information(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        guidepost = "tourism=information & information=guidepost {name '${name}' | '${ref}' | 'указатель'} [0x4c00 resolution 23]"
        route_marker = "tourism=information & information=route_marker {name '${name}' | '${ref}' | 'маркер'} [0x4c00 resolution 24]"
        generic = "tourism=information {name '${name}' | 'информация'} [0x4c00 resolution 24]"
        self.assertIn(guidepost, points)
        self.assertIn(route_marker, points)
        self.assertIn(generic, points)
        self.assertLess(points.index(guidepost), points.index(generic))
        self.assertLess(points.index(route_marker), points.index(generic))

if __name__ == '__main__':
    unittest.main()

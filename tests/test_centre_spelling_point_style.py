from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class CentreSpellingPointStyleTests(unittest.TestCase):
    def test_equivalent_centre_spelling_variants_share_rules(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        active = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )

        conference = '(amenity=conference_centre | amenity=convention_center) [0x2c09 resolution 24]'
        community = '(amenity=community_centre | amenity=community_center) [0x3005 resolution 24]'
        self.assertIn(conference, active)
        self.assertIn(community, active)

        rest = active.replace(conference, '').replace(community, '')
        self.assertNotIn('amenity=conference_centre [0x2c09 resolution 24]', rest)
        self.assertNotIn('amenity=convention_center [0x2c09 resolution 24]', rest)
        self.assertNotIn('amenity=community_centre [0x3005 resolution 24]', rest)
        self.assertNotIn('amenity=community_center [0x3005 resolution 24]', rest)


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'styles' / 'uralla' / 'points'


class HistoricAttractionFallbackTests(unittest.TestCase):
    def test_historic_attractions_use_normal_attraction_fallback(self) -> None:
        points = POINTS.read_text(encoding='utf-8')
        active_points = '\n'.join(
            line for line in points.splitlines() if not line.lstrip().startswith('#')
        )

        self.assertNotIn(
            'tourism=attraction & historic=* [0x2c02 resolution 24]',
            active_points,
        )
        self.assertIn(
            'tourism=attraction [0x2c04 resolution 24 continue]',
            active_points,
        )


if __name__ == '__main__':
    unittest.main()

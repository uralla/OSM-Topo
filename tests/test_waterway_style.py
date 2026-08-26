from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WATER_LINES = ROOT / 'styles' / 'uralla' / 'inc' / 'water_lines'


class WaterwayStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WATER_LINES.read_text(encoding='utf-8')

    def test_river_keeps_distinct_visual_class(self) -> None:
        self.assertIn('waterway=river & length()>500 [0x01f resolution 20 continue]', self.text)
        self.assertIn('waterway=river & length()<=500 [0x01f resolution 23]', self.text)
        self.assertNotIn('waterway=canal & length()>500 [0x01f', self.text)

    def test_stream_drain_and_canal_share_visual_hierarchy(self) -> None:
        group = '(waterway=stream | waterway=drain | waterway=canal)'
        self.assertIn(group + ' & length()>500 [0x18 resolution 21-23 continue]', self.text)
        self.assertIn(group + ' [0x19 resolution 24 continue]', self.text)
        self.assertNotIn('waterway=drain [0x10109', self.text)

    def test_ditch_remains_close_zoom_only(self) -> None:
        self.assertIn('waterway=ditch [0x10109 resolution 24 continue]', self.text)
        self.assertNotIn('waterway=ditch [0x10109 resolution 21', self.text)

    def test_intermittent_stream_and_drain_keep_custom_dash(self) -> None:
        self.assertIn('(waterway=stream | waterway=drain) & intermittent=yes [0x10f1d resolution 23-23 continue]', self.text)
        self.assertIn('(waterway=stream | waterway=drain) & intermittent=yes [0x10f1e resolution 24]', self.text)


if __name__ == '__main__':
    unittest.main()

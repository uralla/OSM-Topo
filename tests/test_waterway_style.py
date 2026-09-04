from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WATER_LINES = ROOT / 'styles' / 'uralla' / 'inc' / 'water_lines'


class WaterwayStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WATER_LINES.read_text(encoding='utf-8')

    def test_water_routing_carrier_is_removed(self) -> None:
        self.assertNotIn('[0x0f road_class=0 road_speed=0', self.text)
        self.assertNotIn('{add access=no; add taxi=yes}', self.text)

    def test_ranked_rivers_keep_progressive_landmark_lod(self) -> None:
        self.assertIn(
            'uralla:river_rank=1 { set uralla:river_landmark=yes } [0x18 resolution 16-19 continue]',
            self.text,
        )
        self.assertIn(
            'uralla:river_rank=2 { set uralla:river_landmark=yes } [0x18 resolution 17-19 continue]',
            self.text,
        )
        self.assertIn(
            'uralla:river_rank=3 { set uralla:river_landmark=yes } [0x18 resolution 18-19 continue]',
            self.text,
        )
        self.assertIn('uralla:river_landmark=yes [0x19 resolution 20-21 continue]', self.text)
        self.assertIn('uralla:river_landmark=yes [0x01f resolution 22-24]', self.text)

    def test_regional_river_fallback_joins_landmark_lod(self) -> None:
        self.assertIn(
            "| waterway=river & name='Кожим' & length()>500 { set uralla:river_landmark=yes } [0x18 resolution 18-19 continue]",
            self.text,
        )

    def test_ordinary_river_reaches_three_pixel_line_only_at_24(self) -> None:
        self.assertIn(
            'waterway=river & uralla:river_landmark!=yes & length()>500 [0x18 resolution 20-21 continue]',
            self.text,
        )
        self.assertIn(
            'waterway=river & uralla:river_landmark!=yes [0x19 resolution 22-23 continue]',
            self.text,
        )
        self.assertIn(
            'waterway=river & uralla:river_landmark!=yes [0x01f resolution 24]',
            self.text,
        )
        self.assertNotIn('waterway=river & length()>500 [0x01f resolution 20', self.text)

    def test_stream_lod_is_progressive_and_separate_from_drain_canal(self) -> None:
        self.assertIn(
            'waterway=stream & intermittent!=yes & length()>500 [0x18 resolution 21-22 continue]',
            self.text,
        )
        self.assertIn(
            'waterway=stream & intermittent!=yes [0x19 resolution 23 continue]',
            self.text,
        )
        self.assertIn(
            'waterway=stream & intermittent!=yes [0x01f resolution 24]',
            self.text,
        )

    def test_intermittent_stream_and_drain_keep_thin_then_thick_dash(self) -> None:
        self.assertIn(
            '(waterway=stream | waterway=drain) & intermittent=yes [0x10f1d resolution 23-23 continue]',
            self.text,
        )
        self.assertIn(
            '(waterway=stream | waterway=drain) & intermittent=yes [0x10f1e resolution 24]',
            self.text,
        )

    def test_drain_and_canal_are_left_on_current_hierarchy_pending_review(self) -> None:
        group = '(waterway=drain | waterway=canal)'
        self.assertIn(group + ' & length()>500 [0x18 resolution 21-23 continue]', self.text)
        self.assertIn(group + ' [0x19 resolution 24 continue]', self.text)

    def test_ditch_remains_close_zoom_only(self) -> None:
        self.assertIn('waterway=ditch [0x10109 resolution 24 continue]', self.text)
        self.assertNotIn('waterway=ditch [0x10109 resolution 21', self.text)


if __name__ == '__main__':
    unittest.main()

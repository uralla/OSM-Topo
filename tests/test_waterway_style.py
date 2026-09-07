from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WATER_LINES = ROOT / 'styles' / 'uralla' / 'inc' / 'water_lines'
TYP = ROOT / 'styles' / 'uralla.txt'


class WaterwayStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WATER_LINES.read_text(encoding='utf-8')
        self.typ = TYP.read_text(encoding='utf-8')

    def _line_typ_block(self, type_code: str) -> str:
        pattern = re.compile(
            rf'\[_line\]\s*\nType={re.escape(type_code)}\n(?:(?!\[end\]).)*\[end\]',
            re.DOTALL,
        )
        match = pattern.search(self.typ)
        self.assertIsNotNone(match, f'missing TYP line {type_code}')
        return match.group(0)

    def test_water_routing_carrier_is_removed(self) -> None:
        self.assertNotIn('[0x0f road_class=0 road_speed=0', self.text)
        self.assertNotIn('{add access=no; add taxi=yes}', self.text)

    def test_typ_widths_match_the_agreed_visual_ladder(self) -> None:
        self.assertIn('LineWidth=1', self._line_typ_block('0x18'))
        self.assertIn('LineWidth=2', self._line_typ_block('0x19'))
        self.assertIn('LineWidth=3', self._line_typ_block('0x1f'))
        self.assertIn('Xpm="32 1 2  1"', self._line_typ_block('0x10f1d'))
        self.assertIn('Xpm="32 2 2  1"', self._line_typ_block('0x10f1e'))

    def test_ranked_rivers_use_thin_far_overview_with_500m_gate(self) -> None:
        self.assertIn(
            'uralla:river_rank=1 & length()>500 [0x18 resolution 16-19 continue]',
            self.text,
        )
        self.assertIn(
            'uralla:river_rank=2 & length()>500 [0x18 resolution 17-19 continue]',
            self.text,
        )
        self.assertIn(
            'uralla:river_rank=3 & length()>500 [0x18 resolution 18-19 continue]',
            self.text,
        )

    def test_landmark_river_ladder_matches_agreed_table(self) -> None:
        expected = (
            'uralla:river_landmark=yes & length()>500 [0x19 resolution 20 continue]',
            'uralla:river_landmark=yes & length()>300 [0x19 resolution 21 continue]',
            'uralla:river_landmark=yes & length()>100 [0x01f resolution 22 continue]',
            'uralla:river_landmark=yes & length()>50 [0x01f resolution 23 continue]',
            'uralla:river_landmark=yes [0x01f resolution 24]',
        )
        for rule in expected:
            with self.subTest(rule=rule):
                self.assertIn(rule, self.text)

    def test_regional_river_fallback_is_landmark_before_length_filtering(self) -> None:
        self.assertIn("| waterway=river & name='Кожим' { set uralla:river_landmark=yes }", self.text)
        self.assertIn(
            'waterway=river & uralla:river_landmark=yes & uralla:river_rank!=* & length()>500 [0x18 resolution 18-19 continue]',
            self.text,
        )

    def test_ordinary_river_ladder_matches_agreed_table(self) -> None:
        expected = (
            'waterway=river & uralla:river_landmark!=yes & length()>500 [0x18 resolution 20 continue]',
            'waterway=river & uralla:river_landmark!=yes & length()>300 [0x18 resolution 21 continue]',
            'waterway=river & uralla:river_landmark!=yes & length()>100 [0x19 resolution 22 continue]',
            'waterway=river & uralla:river_landmark!=yes & length()>50 [0x19 resolution 23 continue]',
            'waterway=river & uralla:river_landmark!=yes [0x01f resolution 24]',
        )
        for rule in expected:
            with self.subTest(rule=rule):
                self.assertIn(rule, self.text)

    def test_ordinary_stream_changes_from_dash_to_solid_as_zoom_increases(self) -> None:
        expected = (
            'waterway=stream & intermittent!=yes & length()>100 [0x10f1d resolution 22 continue]',
            'waterway=stream & intermittent!=yes & length()>50 [0x18 resolution 23 continue]',
            'waterway=stream & intermittent!=yes [0x19 resolution 24]',
        )
        for rule in expected:
            with self.subTest(rule=rule):
                self.assertIn(rule, self.text)
        self.assertNotIn('waterway=stream & intermittent!=yes [0x01f resolution 24]', self.text)

    def test_intermittent_stream_starts_at_23_then_thickens_at_24(self) -> None:
        self.assertIn(
            'waterway=stream & intermittent=yes & length()>50 [0x10f1d resolution 23 continue]',
            self.text,
        )
        self.assertIn(
            'waterway=stream & intermittent=yes [0x10f1e resolution 24]',
            self.text,
        )
        self.assertNotIn(
            'waterway=stream & intermittent=yes & length()>100 [0x10f1d resolution 22',
            self.text,
        )

    def test_drain_and_canal_are_left_on_current_hierarchy_pending_review(self) -> None:
        group = '(waterway=drain | waterway=canal)'
        self.assertIn(group + ' & length()>500 [0x18 resolution 21-23 continue]', self.text)
        self.assertIn(group + ' [0x19 resolution 24 continue]', self.text)
        self.assertIn('waterway=drain & intermittent=yes [0x10f1d resolution 23-23 continue]', self.text)
        self.assertIn('waterway=drain & intermittent=yes [0x10f1e resolution 24]', self.text)

    def test_ditch_remains_close_zoom_only(self) -> None:
        self.assertIn('waterway=ditch [0x10109 resolution 24 continue]', self.text)
        self.assertNotIn('waterway=ditch [0x10109 resolution 21', self.text)


if __name__ == '__main__':
    unittest.main()

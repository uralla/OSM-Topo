from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT / 'styles' / 'uralla' / 'lines'
TYP = ROOT / 'styles' / 'uralla.txt'


class AirportLineStyleTests(unittest.TestCase):
    def test_runway_and_taxiway_use_different_line_types(self) -> None:
        lines = LINES.read_text(encoding='utf-8')
        self.assertIn(
            "aeroway=runway & highway!=* & is_closed()=false {name '${ref}'} [0x27 resolution 20]",
            lines,
        )
        self.assertIn(
            "(aeroway=taxiway | aeroway=taxilane) & highway!=* & is_closed()=false {name '${ref}'} [0x1a resolution 23]",
            lines,
        )
        self.assertNotIn(
            "(aeroway=taxiway | aeroway=taxilane) & highway!=* & is_closed()=false {name '${ref}'} [0x27 resolution 23]",
            lines,
        )

    def test_taxiway_typ_type_exists_with_correct_labels(self) -> None:
        typ = TYP.read_text(encoding='utf-8')
        self.assertEqual(typ.count('Type=0x1a'), 1)
        start = typ.index('Type=0x1a')
        end = typ.index('[end]', start)
        block = typ[start:end]
        self.assertIn('String1=0x19,рулёжная дорожка', block)
        self.assertIn('String2=0x04,taxiway', block)


if __name__ == '__main__':
    unittest.main()

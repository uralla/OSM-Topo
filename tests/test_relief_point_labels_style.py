from pathlib import Path
import unittest


RELIEF = Path(__file__).resolve().parents[1] / "styles" / "uralla" / "inc" / "landuse_points"


class ReliefPointLabelStyleTests(unittest.TestCase):
    def test_named_peaks_without_ele_keep_both_lod_levels(self) -> None:
        text = RELIEF.read_text(encoding="utf-8")
        condition = "(natural=peak & ele!=* & name=* & note!=great-peak) | (natural=hill & ele!=* & name=*)"
        self.assertIn(f'{condition} {{name "${{name}}"}} [0x6619 resolution 21-22 continue]', text)
        self.assertIn(f'{condition} {{name "${{name}}"}} [0x6614 resolution 23-24 continue]', text)

    def test_great_peaks_keep_name_when_ele_is_missing(self) -> None:
        text = RELIEF.read_text(encoding="utf-8")
        self.assertIn('note=great-peak & ele!=* {name "${name}"} [0x6616 resolution 23-24]', text)

    def test_volcanoes_keep_name_when_ele_is_missing(self) -> None:
        text = RELIEF.read_text(encoding="utf-8")
        self.assertIn('natural=volcano & note!=great-peak & ele!=* {name "${name}"} [0x2c0c resolution 23-24]', text)


if __name__ == "__main__":
    unittest.main()

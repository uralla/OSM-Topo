from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WATER_POINTS = REPO_ROOT / "styles" / "uralla" / "inc" / "water_points"


class WaterSourceLabelStyleTests(unittest.TestCase):
    def test_normal_water_sources_have_no_generic_water_label(self) -> None:
        text = WATER_POINTS.read_text(encoding="utf-8")
        self.assertNotIn("addlabel 'вода'", text)
        self.assertIn("[0x6511 resolution 22]", text)

    def test_intermittent_water_sources_keep_information_name_without_map_label(self) -> None:
        text = WATER_POINTS.read_text(encoding="utf-8")
        self.assertNotIn("addlabel 'вода (пересых.)'", text)
        self.assertIn("name '${name} (пересых.)' | 'пересых. источник'", text)
        self.assertIn("[0x6512 resolution 23]", text)


if __name__ == "__main__":
    unittest.main()

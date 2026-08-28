from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "styles" / "uralla" / "points"
PRIORITY_POINTS = ROOT / "styles" / "uralla" / "inc" / "priority_points"
WATER_POINTS = ROOT / "styles" / "uralla" / "inc" / "water_points"
NAME_RULES = ROOT / "styles" / "uralla" / "inc" / "name"


class GenericPoiLabelStyleTests(unittest.TestCase):
    def test_generic_default_names_are_not_forced(self) -> None:
        text = POINTS.read_text(encoding="utf-8")
        for generic in ("Посольство", "Телефон", "Туалет", "Сервис"):
            self.assertNotIn(f"default_name '{generic}'", text)

    def test_technical_pois_keep_real_names_instead_of_forced_generic_names(self) -> None:
        text = POINTS.read_text(encoding="utf-8")
        for generic in (
            "башня связи",
            "антенна",
            "башня/труба",
            "водонапорная башня",
            "очистные",
        ):
            self.assertNotIn(f'name "{generic}"', text)
        self.assertIn("name=* { name '${name}' }", text)

    def test_priority_pois_prefer_real_or_data_derived_names(self) -> None:
        text = PRIORITY_POINTS.read_text(encoding="utf-8")
        self.assertNotIn("default_name 'избушка'", text)
        self.assertNotIn("| 'памятник'", text)
        self.assertNotIn("| 'АЗС (продукты)'", text)
        self.assertIn("historic=memorial { name '${name}' | '${inscription}' }", text)
        self.assertIn("amenity=signpost { name '${name}' | '${label}' }", text)

    def test_water_point_has_no_generic_map_label(self) -> None:
        text = WATER_POINTS.read_text(encoding="utf-8")
        self.assertIn("amenity=water_point [0x5001 resolution 23]", text)
        self.assertNotIn("addlabel 'запас воды'", text)

    def test_fuel_details_do_not_become_names_for_unnamed_stations(self) -> None:
        text = NAME_RULES.read_text(encoding="utf-8")
        for synthetic in (
            "       'дизель, газ'",
            "       'дизель'",
            "       'газ'",
            "       'без дизеля, газ'",
            "       'без дизеля'",
        ):
            self.assertNotIn(synthetic, text)
        self.assertIn("'${name} (дизель, газ)'", text)
        self.assertIn("'${operator} (дизель, газ)'", text)


if __name__ == "__main__":
    unittest.main()

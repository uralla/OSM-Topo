from pathlib import Path
import unittest


POINTS = Path(__file__).resolve().parents[1] / "styles" / "uralla" / "points"


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


if __name__ == "__main__":
    unittest.main()

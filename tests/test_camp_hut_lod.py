from pathlib import Path
import unittest

from uralla_build.poi_context import ACCOMMODATION_VALUES, is_accommodation


class CampAndHutLodTests(unittest.TestCase):
    def test_camp_site_uses_hover_fallback_name(self) -> None:
        text = Path("styles/uralla/points").read_text(encoding="utf-8")
        self.assertIn("tourism=camp_site { name '${name}' | 'кемпинг' } [0x2b03 resolution 22]", text)
        self.assertNotIn("mkgmap:label:2='кемпинг'", text)

    def test_huts_are_accommodation_candidates(self) -> None:
        self.assertIn("wilderness_hut", ACCOMMODATION_VALUES)
        self.assertIn("alpine_hut", ACCOMMODATION_VALUES)
        self.assertTrue(is_accommodation({"tourism": "wilderness_hut"}))
        self.assertTrue(is_accommodation({"tourism": "alpine_hut"}))

    def test_huts_have_hml_style_rules(self) -> None:
        text = Path("styles/uralla/inc/priority_points").read_text(encoding="utf-8")
        name_expr = "{ name '$" + "{name}' | 'избушка' }"
        for lod, resolution in (("H", 22), ("M", 23), ("L", 24)):
            expected = (
                f"uralla:poi_lod_class={lod} & (tourism=wilderness_hut | tourism=alpine_hut) "
                + name_expr
                + f" [0x2b07 resolution {resolution}]"
            )
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()

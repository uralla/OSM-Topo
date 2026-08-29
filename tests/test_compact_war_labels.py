from pathlib import Path
import unittest


class CompactWarLabelsTests(unittest.TestCase):
    def test_great_patriotic_war_forms_are_compacted(self) -> None:
        text = Path("styles/uralla/inc/name").read_text(encoding="utf-8")
        expected = (
            "subst:Великая Отечественная война=>ВОВ",
            "subst:Великой Отечественной войны=>ВОВ",
            "subst:Великую Отечественную войну=>ВОВ",
            "subst:Великой Отечественной войне=>ВОВ",
        )
        for rule in expected:
            with self.subTest(rule=rule):
                self.assertIn(rule, text)


if __name__ == "__main__":
    unittest.main()

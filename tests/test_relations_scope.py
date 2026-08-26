from pathlib import Path
import unittest


RELATIONS = Path(__file__).resolve().parents[1] / "styles" / "uralla" / "relations"


class RelationScopeTests(unittest.TestCase):
    def test_irrelevant_networks_are_removed(self) -> None:
        text = RELATIONS.read_text(encoding="utf-8")
        for token in ("network=US:I", "network=US:US", "network~'US:", "Trans African Highway", "network='TAH'"):
            self.assertNotIn(token, text)

    def test_relevant_international_networks_remain(self) -> None:
        text = RELATIONS.read_text(encoding="utf-8")
        self.assertIn("network=e-road", text)
        self.assertIn("network=AsianHighway | network=AH", text)

    def test_tourist_routes_remain(self) -> None:
        text = RELATIONS.read_text(encoding="utf-8")
        self.assertIn("type=route & route=hiking & name=*", text)
        self.assertIn("type=route & (route=bicycle | route=mtb) & name=*", text)


if __name__ == "__main__":
    unittest.main()

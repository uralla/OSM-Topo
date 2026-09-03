from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TUNNELS = ROOT / "styles" / "uralla" / "inc" / "tunnels"
TYP = ROOT / "styles" / "uralla.txt"


class HighwayTunnelTests(unittest.TestCase):
    def _text(self) -> str:
        return TUNNELS.read_text(encoding="utf-8")

    def test_highway_tunnels_use_single_0x08_routable_line(self) -> None:
        text = self._text()
        self.assertIn("[0x08 road_class=", text)
        self.assertNotIn("[0x1b ", text)
        self.assertNotIn("continue]", text)
        for road_type in ("0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07", "0x0a", "0x13"):
            self.assertNotIn(f"[{road_type} ", text)

    def test_major_tunnel_routing_classes_match_ordinary_roads(self) -> None:
        text = self._text()
        expected = (
            "highway=motorway & tunnel=yes [0x08 road_class=4 road_speed=6 resolution 16]",
            "highway=motorway_link & tunnel=yes [0x08 road_class=4 road_speed=4 resolution 19]",
            "highway=trunk & tunnel=yes [0x08 road_class=4 road_speed=6 resolution 14]",
            "highway=trunk_link & tunnel=yes [0x08 road_class=4 road_speed=6 resolution 18]",
            "highway=primary & tunnel=yes [0x08 road_class=3 road_speed=5 resolution 17]",
            "highway=secondary & tunnel=yes [0x08 road_class=2 road_speed=5 resolution 20]",
            "highway=tertiary & tunnel=yes [0x08 road_class=1 road_speed=4 resolution 23]",
        )
        for rule in expected:
            self.assertIn(rule, text)

    def test_tunnel_overview_thresholds_are_softer_than_ordinary_roads(self) -> None:
        text = self._text()
        self.assertIn("highway=secondary & tunnel=yes & length()>250 [0x08 road_class=2 road_speed=5 resolution 18]", text)
        self.assertIn("highway=tertiary & tunnel=yes & length()>250 [0x08 road_class=1 road_speed=4 resolution 19]", text)
        self.assertIn("highway=track & tracktype=grade1 & tunnel=yes & length()>50 [0x08 road_class=0 road_speed=1 resolution 21]", text)
        self.assertIn("highway=track & tracktype!=grade1 & tunnel=yes & length()>50 [0x08 road_class=0 road_speed=1 resolution 22]", text)
        self.assertIn("highway=cycleway & tunnel=yes & length()>100 [0x08 road_class=0 road_speed=1 resolution 22]", text)

    def test_local_tunnel_hierarchy_matches_ordinary_roads(self) -> None:
        text = self._text()
        expected = (
            "highway=minor & tunnel=yes [0x08 road_class=1 road_speed=4 resolution 22]",
            "highway=unclassified & ref=* & tunnel=yes [0x08 road_class=1 road_speed=4 resolution 22]",
            "highway=unclassified & ref!=* & tunnel=yes [0x08 road_class=0 road_speed=3 resolution 23]",
            "highway=living_street & tunnel=yes [0x08 road_class=0 road_speed=2 resolution 24]",
            "highway=residential & tunnel=yes [0x08 road_class=0 road_speed=3 resolution 24]",
            "highway=service & tunnel=yes [0x08 road_class=0 road_speed=2 resolution 24]",
        )
        for rule in expected:
            self.assertIn(rule, text)

    def test_tunnel_0x08_typ_is_nolabel(self) -> None:
        typ = TYP.read_text(encoding="utf-8")
        match = re.search(r"\[_line\]\nType=0x08\n.*?\n\[end\]", typ, re.S)
        self.assertIsNotNone(match)
        assert match is not None
        block = match.group(0)
        self.assertIn("FontStyle=NoLabel", block)


if __name__ == "__main__":
    unittest.main()

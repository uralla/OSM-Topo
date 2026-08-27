from pathlib import Path
import unittest


LINES = Path(__file__).resolve().parents[1] / "styles" / "uralla" / "lines"


class MarkedRouteLineHierarchyTests(unittest.TestCase):
    def test_marked_routes_use_continuous_near_types_before_base_rules(self) -> None:
        text = LINES.read_text(encoding="utf-8")
        expected = (
            "mkgmap:trail_name=* & highway=pedestrian & area!=yes & length()>100 [0x0e road_class=0 road_speed=0 resolution 21-24]",
            "mkgmap:trail_name=* & highway=cycleway & length()>100 [0x0e road_class=0 road_speed=1 resolution 21-24]",
            "mkgmap:trail_name=* & bicycle=yes & highway=path & length()>100 [0x16 road_class=0 road_speed=1 resolution 21-24]",
            "mkgmap:trail_name=* & highway=footway & length()>100 [0x0e road_class=0 road_speed=1 resolution 21-24]",
            "mkgmap:trail_name=* & bicycle!=yes & highway=path & length()>100 [0x16 road_class=0 road_speed=0 resolution 22-24]",
            "mkgmap:trail_name=* & highway=track & tracktype!=grade1 & length()>100 [0x13 road_class=0 road_speed=1 resolution 21-24]",
            "mkgmap:trail_name=* & highway=track & tracktype=grade1 & length()>100 [0x0a road_class=0 road_speed=1 resolution 20-24]",
            "mkgmap:trail_name=* & highway=bridleway & length()>100 [0x16 road_class=0 road_speed=0 resolution 23-24]",
        )
        for rule in expected:
            self.assertIn(rule, text)
            self.assertNotIn(rule[:-1] + " continue]", text)

        first_marked = text.index(expected[0])
        self.assertLess(first_marked, text.index("highway=pedestrian & area!=yes [0x07"))
        self.assertLess(first_marked, text.index("highway=cycleway & length()>200 [0x07"))
        self.assertLess(first_marked, text.index("bicycle=yes & highway=path & length()>100 [0x0b"))
        self.assertLess(first_marked, text.index("highway=track & tracktype!=grade1 & length()>100"))

    def test_unmarked_far_near_matrix_remains_intact(self) -> None:
        text = LINES.read_text(encoding="utf-8")
        for rule in (
            "highway=cycleway & length()>200 [0x07 resolution 22-23 continue]",
            "highway=cycleway [0x0e road_class=0 road_speed=1 resolution 24]",
            "bicycle=yes & highway=path & length()>100 [0x0b resolution 22-23 continue]",
            "bicycle=yes & highway=path [0x16 road_class=0 road_speed=1 resolution 24]",
            "bicycle!=yes & highway=path & length()>100 [0x0b resolution 23-23 continue]",
            "bicycle!=yes & highway=path [0x16 road_class=0 road_speed=0 resolution 24]",
            "highway=track & tracktype=grade1 [0x0a road_class=0 road_speed=1 resolution 24]",
            "highway=track & tracktype!=grade1 [0x13 road_class=0 road_speed=1 resolution 24]",
        ):
            self.assertIn(rule, text)


if __name__ == "__main__":
    unittest.main()

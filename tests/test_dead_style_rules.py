from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla"


class DeadStyleRuleTests(unittest.TestCase):
    def test_settlement_type_rules_live_only_in_place_points(self) -> None:
        points = (STYLE / "points").read_text(encoding="utf-8")
        self.assertIn("include 'inc/place_points';", points)
        self.assertIn("# Settlement rendering is defined entirely in inc/place_points.", points)
        active = []
        for line in points.splitlines():
            if line.lstrip().startswith("#"):
                continue
            active.append(line.split("#", 1)[0])
        active_text = "\n".join(active)
        self.assertNotIn("place=city & mkgmap:area2poi!=true\t[", active_text)
        self.assertNotIn("place=town & mkgmap:area2poi!=true\t[", active_text)
        self.assertNotIn("place=village & mkgmap:area2poi!=true\t[", active_text)
        self.assertNotIn("place=locality & mkgmap:area2poi!=true\t[", active_text)

    def test_cave_entrance_has_only_priority_rule(self) -> None:
        priority = (STYLE / "inc" / "priority_points").read_text(encoding="utf-8")
        landuse = (STYLE / "inc" / "landuse_points").read_text(encoding="utf-8")
        self.assertIn("natural=cave_entrance & name=* { set mkgmap:label:1=' ' } [0x6608 resolution 23]", priority)
        self.assertIn("natural=cave_entrance { set mkgmap:label:1=' ' } [0x6608 resolution 24]", priority)
        self.assertNotIn("natural=cave_entrance [0x11602", priority)
        self.assertNotIn("natural=cave_entrance [0x6601", landuse)

    def test_residential_polygon_has_no_unreachable_duplicate(self) -> None:
        landuse = (STYLE / "inc" / "landuse_polygons").read_text(encoding="utf-8")
        self.assertIn("landuse=residential [0x10 resolution 21-21 continue]", landuse)
        self.assertIn("landuse=residential [0x03 resolution 22]", landuse)
        self.assertNotIn("boundary=administrative & landuse=residential [0x03", landuse)

    def test_boundary_name_is_assigned_once(self) -> None:
        lines = (STYLE / "lines").read_text(encoding="utf-8")
        rule = "boundary=administrative { name '${mkgmap:boundary_name}' }"
        self.assertEqual(lines.count(rule), 1)
        self.assertNotIn("boundary=administrative & place!=* { name '${mkgmap:boundary_name}' }", lines)


if __name__ == "__main__":
    unittest.main()

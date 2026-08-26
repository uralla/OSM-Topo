from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
ACCESS = REPO_ROOT / "styles" / "uralla" / "inc" / "access"
LINES = REPO_ROOT / "styles" / "uralla" / "lines"


class PlatformRoutingStyleTests(unittest.TestCase):
    def test_platform_allows_foot_and_bicycle_but_keeps_generic_access_closed(self) -> None:
        text = ACCESS.read_text(encoding="utf-8")
        rule = "railway=platform                           { add bicycle=yes; add foot=yes; add access=no }"
        self.assertIn(rule, text)
        self.assertLess(text.index(rule), text.index("# Copy the OSM access tags to the mkgmap internal tags"))
        self.assertLess(text.index(rule), text.index("access=* { addaccess '${access}' }"))

    def test_platform_line_keeps_minimal_routing_class(self) -> None:
        text = LINES.read_text(encoding="utf-8")
        self.assertIn(
            "railway=platform & area!=yes [0x16 road_class=0 road_speed=0 resolution 24 continue]",
            text,
        )


if __name__ == "__main__":
    unittest.main()

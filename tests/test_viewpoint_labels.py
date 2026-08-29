from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "styles" / "uralla" / "points"
PRIORITY_POINTS = ROOT / "styles" / "uralla" / "inc" / "priority_points"


class ViewpointLabelTests(unittest.TestCase):
    def test_named_viewpoint_keeps_real_name(self) -> None:
        text = PRIORITY_POINTS.read_text(encoding="utf-8")
        self.assertIn(
            "tourism=viewpoint & name=* { name '${name}' } [0x2c04 resolution 23]",
            text,
        )

    def test_unnamed_viewpoint_is_unlabeled_on_map_but_explained_in_details(self) -> None:
        text = PRIORITY_POINTS.read_text(encoding="utf-8")
        self.assertIn(
            "tourism=viewpoint & name!=* { set mkgmap:label:1=' '; set mkgmap:label:2='видовая точка' } [0x2c04 resolution 23]",
            text,
        )
        self.assertNotIn("| 'видовая точка'", text)

    def test_legacy_later_viewpoint_rules_cannot_override_priority_rules(self) -> None:
        points = POINTS.read_text(encoding="utf-8")
        self.assertIn("include 'inc/priority_points';", points)
        self.assertLess(
            points.index("include 'inc/priority_points';"),
            points.index("tourism=viewpoint & name=*"),
        )


if __name__ == "__main__":
    unittest.main()

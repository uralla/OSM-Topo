from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "styles" / "uralla" / "points"


class ViewpointLabelTests(unittest.TestCase):
    def test_named_viewpoint_keeps_real_name(self) -> None:
        text = POINTS.read_text(encoding="utf-8")
        self.assertIn(
            "tourism=viewpoint & name=* { name '${name}' } [0x2c04 resolution 23]",
            text,
        )

    def test_unnamed_viewpoint_is_icon_only(self) -> None:
        text = POINTS.read_text(encoding="utf-8")
        self.assertIn(
            "tourism=viewpoint & name!=* { set mkgmap:label:1=' ' } [0x2c04 resolution 23]",
            text,
        )
        self.assertNotIn("tourism=viewpoint {name '${name}' | 'видовая точка'}", text)


if __name__ == "__main__":
    unittest.main()

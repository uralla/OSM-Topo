from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROAD_DENSITY = ROOT / "styles" / "uralla" / "inc" / "road_density"


class TrackContinuityStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = ROAD_DENSITY.read_text(encoding="utf-8")

    def test_sparse_tracks_do_not_require_way_length(self) -> None:
        self.assertIn(
            "highway=track & tracktype!=grade1 {add mkgmap:display_name = '${name}'} [0x12 resolution 22-23 continue]",
            self.text,
        )
        self.assertIn(
            "highway=track & tracktype=grade1 {add mkgmap:display_name = '${name}'} [0x07 resolution 21-23 continue]",
            self.text,
        )
        self.assertNotIn(
            "highway=track & tracktype!=grade1 & length()>100 {add mkgmap:display_name = '${name}'} [0x12 resolution 22-23 continue]",
            self.text,
        )

    def test_marked_tracks_keep_priority_without_way_length(self) -> None:
        self.assertIn(
            "mkgmap:trail_name=* & highway=track & tracktype!=grade1 {add mkgmap:display_name = '${name}'} [0x12 resolution 21-22 continue]",
            self.text,
        )
        self.assertIn(
            "mkgmap:trail_name=* & highway=track & tracktype=grade1 {add mkgmap:display_name = '${name}'} [0x07 resolution 20-22 continue]",
            self.text,
        )

    def test_dense_track_decluttering_still_uses_length_filter(self) -> None:
        self.assertIn(
            "highway=track & tracktype=grade1 & uralla:road_density=dense & length()>100",
            self.text,
        )
        self.assertIn(
            "highway=track & tracktype!=grade1 & uralla:road_density=dense & length()>100",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()

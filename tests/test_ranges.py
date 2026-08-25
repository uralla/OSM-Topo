from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.ranges import validate_generated_range


IDENTITY = {
    "overview_mapnumber": "01018000",
    "first_tile_mapid": "01018001",
    "last_reserved_mapid": "01018999",
}


class RangeTests(unittest.TestCase):
    def test_valid_areas_and_template(self) -> None:
        with TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            areas = tmp_path / "areas.list"
            areas.write_text(
                "01018001: 1,2 to 3,4\n01018002: 5,6 to 7,8\n",
                encoding="utf-8",
            )
            template = tmp_path / "template.args"
            template.write_text(
                "mapname: 01018001\ninput-file: 01018001.osm.pbf\n"
                "mapname: 01018002\ninput-file: 01018002.osm.pbf\n",
                encoding="utf-8",
            )
            issues, report = validate_generated_range("ural-n", IDENTITY, areas, template)
            self.assertEqual(issues, [])
            self.assertEqual(report["tile_count"], 2)
            self.assertEqual(report["remaining_capacity"], 997)

    def test_gap_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            areas = Path(directory) / "areas.list"
            areas.write_text(
                "01018001: 1,2 to 3,4\n01018003: 5,6 to 7,8\n",
                encoding="utf-8",
            )
            issues, _ = validate_generated_range("ural-n", IDENTITY, areas)
            self.assertTrue(any("not contiguous" in issue.message for issue in issues))

    def test_overflow_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            areas = Path(directory) / "areas.list"
            areas.write_text(
                "01018001: 1,2 to 3,4\n01019000: 5,6 to 7,8\n",
                encoding="utf-8",
            )
            issues, _ = validate_generated_range("ural-n", IDENTITY, areas)
            self.assertTrue(any("exceeds" in issue.message for issue in issues))


if __name__ == "__main__":
    unittest.main()

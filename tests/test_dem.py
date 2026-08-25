from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uralla_build.dem import format_hgt_name, parse_hgt_name, read_poly, select_dem_files, tiles_for_polygon


class DemSelectionTests(unittest.TestCase):
    def test_hgt_names_use_southwest_corner(self) -> None:
        self.assertEqual(parse_hgt_name("N00E006.hgt"), (0, 6))
        self.assertEqual(parse_hgt_name("nested/S01W001.hgt"), (-1, -1))
        self.assertEqual(format_hgt_name(-1, -1), "S01W001.hgt")
        self.assertEqual(format_hgt_name(10, 180), "N10W180.hgt")

    def test_polygon_selects_only_cells_with_area_intersection(self) -> None:
        with TemporaryDirectory() as directory:
            polygon = Path(directory) / "square.poly"
            polygon.write_text(
                "square\n1\n 0.2 0.2\n 1.2 0.2\n 1.2 1.2\n 0.2 1.2\n 0.2 0.2\nEND\nEND\n",
                encoding="utf-8",
            )
            tiles = tiles_for_polygon(read_poly(polygon))
            self.assertEqual(tiles, {(0, 0), (0, 1), (1, 0), (1, 1)})

    def test_integer_boundary_does_not_add_an_outside_cell(self) -> None:
        with TemporaryDirectory() as directory:
            polygon = Path(directory) / "square.poly"
            polygon.write_text(
                "square\n1\n 0 0\n 1 0\n 1 1\n 0 1\n 0 0\nEND\nEND\n",
                encoding="utf-8",
            )
            self.assertEqual(tiles_for_polygon(read_poly(polygon)), {(0, 0)})

    def test_polygon_crossing_dateline_uses_both_edge_tiles(self) -> None:
        with TemporaryDirectory() as directory:
            polygon = Path(directory) / "dateline.poly"
            polygon.write_text(
                "dateline\n1\n 179.8 10.2\n -179.8 10.2\n -179.8 10.8\n 179.8 10.8\n 179.8 10.2\nEND\nEND\n",
                encoding="utf-8",
            )
            self.assertEqual(tiles_for_polygon(read_poly(polygon)), {(10, 179), (10, -180)})

    def test_manifest_filter_and_halo(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            poly = root / "poly"
            poly.mkdir()
            (poly / "active.poly").write_text(
                "active\n1\n 0.2 0.2\n 0.8 0.2\n 0.8 0.8\n 0.2 0.8\nEND\nEND\n",
                encoding="utf-8",
            )
            inventory = root / "dem.tsv"
            inventory.write_text(
                "N00E000.hgt\t10\nN00E001.hgt\t11\nN01E000.hgt\t12\nN01E001.hgt\t13\nignored.aux.xml\t2\n",
                encoding="utf-8",
            )
            manifest = {
                "defaults": {"enabled": True},
                "products": {
                    "active": {"polygon": "poly/active.poly", "elevation": "elevation/a.pbf"},
                    "flat": {"polygon": "poly/missing.poly", "elevation": None},
                },
            }
            selection = select_dem_files(manifest, inventory, root, halo=1)
            self.assertEqual(selection.elevation_products, ("active",))
            self.assertEqual(selection.exact_files, ("N00E000.hgt",))
            self.assertEqual(
                selection.selected_files,
                ("N00E000.hgt", "N00E001.hgt", "N01E000.hgt", "N01E001.hgt"),
            )
            self.assertEqual(selection.selected_bytes, 46)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tools" / "style-typ-audit.py"
SPEC = importlib.util.spec_from_file_location("style_typ_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class StyleTypAuditTests(unittest.TestCase):
    def test_combined_style_code_splits_to_typ_type_and_subtype(self) -> None:
        self.assertEqual(AUDIT.split_style_code("0x1341f"), (0x134, 0x1F))
        self.assertEqual(AUDIT.split_style_code("0x1615"), (0x16, 0x15))
        self.assertEqual(AUDIT.split_style_code("0x1f"), (0x1F, 0))

    def test_style_collection_follows_root_relative_nested_includes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inc").mkdir()
            (root / "points").write_text(
                "include 'inc/priority';\namenity=school [0x2c05 resolution 24]\n",
                encoding="utf-8",
            )
            (root / "inc/priority").write_text(
                "include 'inc/shared';\nnatural=spring [0x6511 resolution 22]\n",
                encoding="utf-8",
            )
            (root / "inc/shared").write_text(
                "railway=signal [0x1341f resolution 24]\n",
                encoding="utf-8",
            )
            self.assertEqual(
                AUDIT.collect_style_codes(root, "points"),
                {(0x2C, 0x05), (0x65, 0x11), (0x134, 0x1F)},
            )

    def test_typ_parser_understands_split_extended_codes(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.txt"
            path.write_bytes(
                """[_point]\nType=0x065\nSubType=0x11\nString1=0x19,источник\n[End]\n\n[_line]\nType=0x134\nSubType=0x1f\n[End]\n""".encode("cp1251")
            )
            parsed = AUDIT.parse_typ_codes(path)
            self.assertEqual(parsed["point"], {(0x65, 0x11)})
            self.assertEqual(parsed["line"], {(0x134, 0x1F)})

    def test_duplicate_visual_groups_ignore_labels_but_keep_visual_directives(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.txt"
            path.write_bytes(
                """[_point]\nType=0x065\nSubType=0x11\nString1=0x19,источник\nFontStyle=NoLabel (invisible)\nXpm=\"0 0 1 0\"\n\"1 c #FFFFFF\"\n[End]\n\n[_point]\nType=0x065\nSubType=0x12\nString1=0x19,пересыхающий источник\nFontStyle=NoLabel (invisible)\nXpm=\"0 0 1 0\"\n\"1 c #FFFFFF\"\n[End]\n\n[_point]\nType=0x065\nSubType=0x13\nFontStyle=NormalFont\nXpm=\"0 0 1 0\"\n\"1 c #FFFFFF\"\n[End]\n""".encode("cp1251")
            )
            groups = AUDIT.duplicate_visual_groups(path)
            self.assertIn([(0x65, 0x11), (0x65, 0x12)], groups["point"])
            self.assertFalse(any((0x65, 0x13) in group for group in groups["point"]))


if __name__ == "__main__":
    unittest.main()

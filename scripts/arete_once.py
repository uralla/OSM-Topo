from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
needle = "natural=ridge & name!=* [0x10e01 resolution 24]\nnatural=cliff [0x10f17 resolution 23 continue]"
replacement = "natural=ridge & name!=* [0x10e01 resolution 24]\n# Arêtes are narrow rocky crests; keep them as close-zoom ridge-like topo lines.\nnatural=arete [0x10e01 resolution 24]\nnatural=cliff [0x10f17 resolution 23 continue]"
if lines.count(needle) != 1:
    raise SystemExit(f'expected one ridge/cliff insertion point, got {lines.count(needle)}')
lines = lines.replace(needle, replacement, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
insert = "    def test_arrete_is_visible_only_at_close_zoom(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        self.assertIn(\"natural=arete [0x10e01 resolution 24]\", lines)\n        self.assertNotRegex(lines, r\"natural=arete .*resolution (?:1[0-9]|2[0-3])\")\n\n"
marker = "    def test_ridge_lod_is_non_overlapping_and_unnamed_is_close_zoom_only(self) -> None:\n"
if insert not in test:
    if test.count(marker) != 1:
        raise SystemExit('test insertion marker not found')
    test = test.replace(marker, insert + marker, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
old_overlay = "highway=* & tunnel=yes | railway=* & tunnel=yes [0x10e04 resolution 24 continue]"
new_overlay = "highway=* & tunnel=yes | railway=* & tunnel=yes & !(railway=light_rail & layer<0) [0x10e04 resolution 24 continue]"
if lines.count(old_overlay) != 1:
    raise SystemExit(f'expected one tunnel overlay rule, got {lines.count(old_overlay)}')
lines = lines.replace(old_overlay, new_overlay, 1)
old_preserved = "(railway=preserved) & !(tunnel=yes) [0x10e1a resolution 24]"
new_preserved = "railway=preserved [0x10e1a resolution 24]"
if lines.count(old_preserved) != 1:
    raise SystemExit(f'expected one preserved railway rule, got {lines.count(old_preserved)}')
lines = lines.replace(old_preserved, new_preserved, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor = "    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:\n"
if anchor not in test:
    raise SystemExit('test anchor not found')
block = '''    def test_railway_tunnel_overlay_never_becomes_orphan(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        overlay = "highway=* & tunnel=yes | railway=* & tunnel=yes & !(railway=light_rail & layer<0) [0x10e04 resolution 24 continue]"\n        preserved = "railway=preserved [0x10e1a resolution 24]"\n        self.assertIn(overlay, lines)\n        self.assertIn(preserved, lines)\n        self.assertNotIn("(railway=preserved) & !(tunnel=yes) [0x10e1a resolution 24]", lines)\n        self.assertLess(lines.index(overlay), lines.index(preserved))\n        self.assertIn("railway=light_rail & !(layer<0) [0x10f14 resolution 22-24]", lines)\n\n'''
if 'def test_railway_tunnel_overlay_never_becomes_orphan' not in test:
    test = test.replace(anchor, block + anchor, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

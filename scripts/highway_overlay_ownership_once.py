from pathlib import Path

LINES = Path('styles/uralla/lines')
TEST = Path('tests/test_line_fallback_cleanup.py')

lines = LINES.read_text(encoding='utf-8')
late = '''# Hide proposed ways
(highway=proposed | highway=proposal | highway=planned | highway ~ '.*proposed.*') {delete highway;delete junction}
# Hide removed ways
(highway=razed | highway=dismantled) {deletealltags}
# Hide abandoned ways. Abandoned highways have some evidence of their former existence but are no longer used.
# ((abandoned:highway=* & highway!=*) | highway=abandoned) {deletealltags}
# Hide other non-existent ways
# (highway=unbuilt | highway=neverbuilt | highway=rejected | highway ~ 'x-.*') {delete highway;delete junction}
# Remove highway tag from ways which are not suitable for routing
highway=traffic_signals | highway=junction | highway=island | highway=centre_line | highway=traffic_island | highway=stopline {delete highway}
highway=piste | highway=ski {delete highway}
highway=no | highway=none {delete highway}

# Hide unaccessible tunnels
highway=* & tunnel=yes & (access=private|access=no)
& foot!=* & bicycle!=* {delete highway;delete junction}

'''
if lines.count(late) != 1:
    raise SystemExit(f'expected one late highway filter block, got {lines.count(late)}')
lines = lines.replace(late, '', 1)
anchor = '''# Disused/abandoned roads are useful topo landmarks but must never enter active routing.
'''
if anchor not in lines:
    raise SystemExit('lifecycle anchor not found')
filters = '''# Remove non-existent/non-way highway classes before any active visual overlay can emit.
(highway=proposed | highway=proposal | highway=planned | highway ~ '.*proposed.*') {delete highway;delete junction}
(highway=razed | highway=dismantled) {deletealltags}
highway=traffic_signals | highway=junction | highway=island | highway=centre_line | highway=traffic_island | highway=stopline {delete highway}
highway=piste | highway=ski {delete highway}
highway=no | highway=none {delete highway}
# Hide inaccessible highway tunnels before tunnel/bridge/oneway overlays.
highway=* & tunnel=yes & (access=private|access=no) & foot!=* & bicycle!=* {delete highway;delete junction}

'''
lines = lines.replace(anchor, filters + anchor, 1)
lines = lines.replace(
    "highway!=path & highway!=footway & highway!=cycleway & highway!=bridleway & highway!=steps & highway!=pedestrian\n& (smoothness=very_horrible | smoothness=impassable | smoothness=horrible)",
    "highway=* & highway!=path & highway!=footway & highway!=cycleway & highway!=bridleway & highway!=steps & highway!=pedestrian\n& (smoothness=very_horrible | smoothness=impassable | smoothness=horrible)",
    1,
)
lines = lines.replace(
    "highway!=path & highway!=footway & highway!=cycleway & highway!=bridleway & highway!=steps & highway!=pedestrian\n& (smoothness=bad | smoothness=very_bad)",
    "highway=* & highway!=path & highway!=footway & highway!=cycleway & highway!=bridleway & highway!=steps & highway!=pedestrian\n& (smoothness=bad | smoothness=very_bad)",
    1,
)
old_bridge = "(bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path\n\t& area!=yes [0x10f16 resolution 24 continue]"
new_bridge = "highway=* & (bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path\n\t& area!=yes [0x10f16 resolution 24 continue]"
if lines.count(old_bridge) != 1:
    raise SystemExit(f'expected one motor bridge overlay, got {lines.count(old_bridge)}')
lines = lines.replace(old_bridge, new_bridge, 1)
LINES.write_text(lines, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
anchor_test = "    def test_power_line_predicates_have_no_redundant_cutline_subset(self) -> None:\n"
if anchor_test not in test:
    raise SystemExit('test anchor not found')
block = '''    def test_removed_highways_cannot_leak_active_overlays(self) -> None:\n        lines = LINES.read_text(encoding='utf-8')\n        planned = "(highway=proposed | highway=proposal | highway=planned | highway ~ '.*proposed.*') {delete highway;delete junction}"\n        smooth = "highway=* & highway!=path & highway!=footway & highway!=cycleway & highway!=bridleway & highway!=steps & highway!=pedestrian"\n        bridge = "highway=* & (bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path"\n        oneway = "highway=* & oneway=yes & highway!=construction & highway!=proposed"\n        tunnel = "highway=* & tunnel=yes | railway=* & tunnel=yes & !(railway=light_rail & layer<0)"\n        self.assertIn(planned, lines)\n        self.assertIn(smooth, lines)\n        self.assertIn(bridge, lines)\n        self.assertLess(lines.index(planned), lines.index(smooth))\n        self.assertLess(lines.index(planned), lines.index(oneway))\n        self.assertLess(lines.index(planned), lines.index(bridge))\n        self.assertLess(lines.index(planned), lines.index(tunnel))\n        self.assertNotIn("(bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path", lines)\n\n'''
if 'def test_removed_highways_cannot_leak_active_overlays' not in test:
    test = test.replace(anchor_test, block + anchor_test, 1)
TEST.write_text(test, encoding='utf-8', newline='\n')

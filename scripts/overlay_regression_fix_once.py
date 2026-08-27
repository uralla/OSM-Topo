from pathlib import Path

LINE_TEST = Path('tests/test_line_fallback_cleanup.py')
TUNNEL_TEST = Path('tests/test_tunnel_overlay_order.py')

text = LINE_TEST.read_text(encoding='utf-8')
old = '        self.assertNotIn("(bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path", lines)\n'
new = '        self.assertNotIn("\\n(bridge=yes | bridge=true) & highway!=pedestrian & highway!=footway & highway!=path", lines)\n'
if old not in text:
    raise SystemExit('bridge assertion not found')
LINE_TEST.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')

text = TUNNEL_TEST.read_text(encoding='utf-8')
old = '        overlay = "highway=* & tunnel=yes | railway=* & tunnel=yes [0x10e04 resolution 24 continue]"\n'
new = '        overlay = "highway=* & tunnel=yes | railway=* & tunnel=yes & !(railway=light_rail & layer<0) [0x10e04 resolution 24 continue]"\n'
if old not in text:
    raise SystemExit('old tunnel overlay expectation not found')
TUNNEL_TEST.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')

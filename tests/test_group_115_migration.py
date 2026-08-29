from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla"
TYP = ROOT / "styles" / "uralla.txt"
INCLUDE_RE = re.compile(r"^\s*include\s+'([^']+)'\s*;", re.MULTILINE)
STYLE_115_RE = re.compile(r"\[0x115([0-9a-fA-F]{2})\b")
TYP_115_RE = re.compile(r"(?ms)^\[_point\]\s*\nType=0x115\s*\nSubType=0x([0-9a-fA-F]{2})\b.*?^\[end\]")

def production_files():
    result, seen = [], set()
    def visit(path):
        path = path.resolve()
        if path in seen: return
        seen.add(path); result.append(path)
        for relative in INCLUDE_RE.findall(path.read_text(encoding="utf-8")):
            visit(STYLE / relative)
    visit(STYLE / "points")
    return result

class Group115MigrationTests(unittest.TestCase):
    def test_no_live_group_115_style_or_typ(self):
        found = set()
        for path in production_files():
            found.update(STYLE_115_RE.findall(path.read_text(encoding="utf-8")))
        self.assertEqual(set(), found)
        self.assertEqual(set(), set(TYP_115_RE.findall(TYP.read_text(encoding="utf-8"))))

if __name__ == "__main__": unittest.main()

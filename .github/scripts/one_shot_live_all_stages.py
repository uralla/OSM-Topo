from pathlib import Path

p = Path('uralla_build/runner.py')
s = p.read_text(encoding='utf-8')
old = '''LIVE_OUTPUT_STAGES = frozenset({"preprocess", "prepare-tiles", "mkgmap"})\n'''
new = '''# All pipeline stages stream stdout/stderr live while also writing durable logs.\n'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)
old2 = '''        live = stage in LIVE_OUTPUT_STAGES\n        threads: list[threading.Thread] = []\n'''
new2 = '''        live = True\n        threads: list[threading.Thread] = []\n'''
assert s.count(old2) == 1, s.count(old2)
s = s.replace(old2, new2, 1)
p.write_text(s, encoding='utf-8')

Path('tests/test_live_stage_output.py').write_text('''from pathlib import Path\nimport unittest\n\nROOT = Path(__file__).resolve().parents[1]\n\nclass LiveStageOutputTests(unittest.TestCase):\n    def test_all_stages_stream_live_output(self):\n        text = (ROOT / "uralla_build/runner.py").read_text(encoding="utf-8")\n        self.assertNotIn("LIVE_OUTPUT_STAGES", text)\n        self.assertIn("live = True", text)\n        self.assertIn("stdout=subprocess.PIPE if live else stdout_handle", text)\n        self.assertIn("stderr=subprocess.PIPE if live else stderr_handle", text)\n        self.assertIn("_wait_with_heartbeat(process, stage, started)", text)\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8')

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class LiveStageOutputTests(unittest.TestCase):
    def test_all_stages_stream_live_output(self):
        text = (ROOT / "uralla_build/runner.py").read_text(encoding="utf-8")
        self.assertNotIn("LIVE_OUTPUT_STAGES", text)
        self.assertIn("live = True", text)
        self.assertIn("stdout=subprocess.PIPE if live else stdout_handle", text)
        self.assertIn("stderr=subprocess.PIPE if live else stderr_handle", text)
        self.assertIn("_wait_with_heartbeat(process, stage, started)", text)

if __name__ == "__main__":
    unittest.main()

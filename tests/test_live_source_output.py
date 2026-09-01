from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_source_refresh_uses_live_flushed_output():
    text = (ROOT / "uralla_build/cli.py").read_text(encoding="utf-8")
    assert 'print(message, flush=True)' in text
    assert 'print(f"Checking OSM source for {args.product}: {source_key}", flush=True)' in text
    assert 'reporter=live_reporter' in text

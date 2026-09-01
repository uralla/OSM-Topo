from pathlib import Path

p = Path('uralla_build/cli.py')
s = p.read_text(encoding='utf-8')
old = '''        if args.apply and getattr(args, "from_stage", None) != "mkgmap":
            source_key = product.get("source")
            if not isinstance(source_key, str):
                raise StageError(f"product {args.product!r} has no source")
            if not args.json:
                print(f"Checking OSM source for {args.product}: {source_key}")
            source_result = refresh_osm_source(
                manifest, host, source_key, reporter=None if args.json else print
            )
            if source_result.status == "error":
                raise StageError(source_result.detail)
'''
new = '''        if args.apply and getattr(args, "from_stage", None) != "mkgmap":
            source_key = product.get("source")
            if not isinstance(source_key, str):
                raise StageError(f"product {args.product!r} has no source")
            live_reporter = None
            if not args.json:
                def live_reporter(message: str) -> None:
                    print(message, flush=True)
                print(f"Checking OSM source for {args.product}: {source_key}", flush=True)
            source_result = refresh_osm_source(
                manifest, host, source_key, reporter=live_reporter
            )
            if source_result.status == "error":
                raise StageError(source_result.detail)
'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Lock the behavior with a source-level regression test: the build CLI must use
# an explicitly flushing reporter for long source downloads.
Path('tests/test_live_source_output.py').write_text('''from pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\ndef test_source_refresh_uses_live_flushed_output():\n    text = (ROOT / "uralla_build/cli.py").read_text(encoding="utf-8")\n    assert 'print(message, flush=True)' in text\n    assert 'print(f"Checking OSM source for {args.product}: {source_key}", flush=True)' in text\n    assert 'reporter=live_reporter' in text\n''', encoding='utf-8')

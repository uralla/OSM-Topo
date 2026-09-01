from pathlib import Path

# 1) Remove duplicate source refresh from the low-level build-product implementation.
cli_path = Path('uralla_build/cli.py')
cli = cli_path.read_text(encoding='utf-8')
old = '''        if args.apply and getattr(args, "from_stage", None) is None:\n            source_key = product.get("source")\n            if not isinstance(source_key, str):\n                raise StageError(f"product {args.product!r} has no source")\n            live_reporter = None\n            if not args.json:\n                def live_reporter(message: str) -> None:\n                    print(message, flush=True)\n                print(f"Checking OSM source for {args.product}: {source_key}", flush=True)\n            source_result = refresh_osm_source(\n                manifest, host, source_key, reporter=live_reporter\n            )\n            if source_result.status == "error":\n                raise StageError(source_result.detail)\n\n'''
if old not in cli:
    raise SystemExit('duplicate source refresh block not found in cli.py')
cli = cli.replace(old, '', 1)
cli_path.write_text(cli, encoding='utf-8')

# 2) Parse the final JSON object from mixed stdout instead of requiring pristine JSON-only output.
ep_path = Path('uralla_build/entrypoint.py')
ep = ep_path.read_text(encoding='utf-8')
insert_after = '''def _format_size(size: int) -> str:\n    value = float(size)\n    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):\n        if value < 1024.0 or unit == "TiB":\n            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"\n        value /= 1024.0\n    return f"{size} B"\n\n\n'''
helper = '''def _last_json_mapping(output: str) -> Mapping[str, object] | None:\n    """Return the final JSON object from mixed human/machine stdout."""\n    decoder = json.JSONDecoder()\n    for index in range(len(output) - 1, -1, -1):\n        if output[index] != "{":\n            continue\n        try:\n            value, end = decoder.raw_decode(output[index:])\n        except json.JSONDecodeError:\n            continue\n        if output[index + end :].strip():\n            continue\n        if isinstance(value, Mapping):\n            return value\n    return None\n\n\n'''
if '_last_json_mapping' not in ep:
    if insert_after not in ep:
        raise SystemExit('entrypoint helper insertion marker not found')
    ep = ep.replace(insert_after, insert_after + helper, 1)

old_parse = '''    try:\n        payload = json.loads(output)\n    except json.JSONDecodeError:\n        print(output)\n        return status\n    if not isinstance(payload, Mapping):\n        print(output)\n        return status\n\n    print(_human_build_summary(payload, manifest, host, product))\n'''
new_parse = '''    payload = _last_json_mapping(output)\n    if payload is None:\n        print(output)\n        return status\n\n    print(_human_build_summary(payload, manifest, host, product))\n'''
if old_parse not in ep:
    raise SystemExit('entrypoint JSON parse block not found')
ep = ep.replace(old_parse, new_parse, 1)
ep_path.write_text(ep, encoding='utf-8')

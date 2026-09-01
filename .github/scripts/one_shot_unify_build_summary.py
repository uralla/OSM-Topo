from pathlib import Path

path = Path('uralla_build/entrypoint.py')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'from .incremental import rebuild_from_mkgmap\n',
    'from .incremental import rebuild_from_mkgmap, rebuild_from_splitter\n',
)

old_guard = '''    if from_stage is not None and from_stage != "mkgmap":\n        print(\n            f"ERROR build-product: --from-stage currently supports only 'mkgmap', got {from_stage!r}",\n            file=sys.stderr,\n        )\n        return 1\n'''
new_guard = '''    if from_stage is not None and from_stage not in {"splitter", "mkgmap"}:\n        print(\n            f"ERROR build-product: --from-stage supports 'splitter' or 'mkgmap', got {from_stage!r}",\n            file=sys.stderr,\n        )\n        return 1\n'''
if old_guard not in text:
    raise SystemExit('legacy from-stage guard not found')
text = text.replace(old_guard, new_guard)

marker = '''    if request is not None and from_stage == "mkgmap":\n'''
splitter_block = '''    if request is not None and from_stage == "splitter":\n        assert manifest is not None and host is not None and product is not None\n        tools_lock = Path(_option_value(arguments, "--tools-lock", "config/tools.lock.yaml"))\n        build_id = _option_value(arguments, "--build-id", "") or None\n        try:\n            payload = rebuild_from_splitter(\n                manifest,\n                host,\n                product_key=product,\n                repo_root=repo_root,\n                manifest_path=manifest_path,\n                tools_lock_path=tools_lock,\n                build_id=build_id,\n            )\n        except (ManifestError, StageError, OSError, ValueError) as exc:\n            print(f"ERROR build-product: {exc}", file=sys.stderr)\n            return 1\n        result = payload.get("result")\n        status = 0 if isinstance(result, Mapping) and result.get("status") == "success" else 1\n        if "--json" in arguments:\n            print(json.dumps({"ok": status == 0, "report": payload}, ensure_ascii=False, indent=2))\n        else:\n            print(_human_build_summary(payload, manifest, host, product))\n        return status\n\n'''
if marker not in text:
    raise SystemExit('mkgmap block marker not found')
text = text.replace(marker, splitter_block + marker, 1)

old_failed = '''    if status != 0 or manifest is None or host is None or product is None:\n        print(output)\n        return status\n\n    try:\n        payload = json.loads(output)\n'''
new_failed = '''    if manifest is None or host is None or product is None:\n        print(output)\n        return status\n\n    try:\n        payload = json.loads(output)\n'''
if old_failed not in text:
    raise SystemExit('raw failed-output branch not found')
text = text.replace(old_failed, new_failed)

old_reused = '''    reused = payload.get("reused_build_id")\n    if isinstance(reused, str) and reused:\n        lines.append(f"  Reused build   {reused} (splitter output)")\n'''
new_reused = '''    reused = payload.get("reused_build_id")\n    if isinstance(reused, str) and reused:\n        from_stage = payload.get("from_stage")\n        reused_kind = "merge checkpoint" if from_stage == "splitter" else "splitter output"\n        lines.append(f"  Reused build   {reused} ({reused_kind})")\n'''
if old_reused not in text:
    raise SystemExit('reused-build summary block not found')
text = text.replace(old_reused, new_reused)

path.write_text(text, encoding='utf-8')

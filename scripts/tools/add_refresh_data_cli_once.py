from pathlib import Path

p = Path('uralla_build/cli.py')
text = p.read_text(encoding='utf-8')

old_import = 'from .errors import ManifestError, StageError, ValidationIssue\n'
new_import = old_import + 'from .external_data import has_refresh_errors, refresh_supplemental_data\n'
if 'from .external_data import has_refresh_errors, refresh_supplemental_data' not in text:
    if old_import not in text:
        raise SystemExit('CLI import anchor not found')
    text = text.replace(old_import, new_import, 1)

anchor = '\ndef _run_stage(args: argparse.Namespace) -> int:\n'
handler = '''\ndef _refresh_data(args: argparse.Namespace) -> int:\n    try:\n        manifest = load_manifest(args.manifest)\n        host = load_host_config(args.host, args.repo_root)\n        results = refresh_supplemental_data(manifest, host)\n    except (ManifestError, OSError) as exc:\n        return _emit([ValidationIssue("refresh-data", str(exc))], None, args.json)\n    if args.json:\n        print(\n            json.dumps(\n                {\n                    "ok": not has_refresh_errors(results),\n                    "results": [result.to_dict() for result in results],\n                },\n                ensure_ascii=False,\n                indent=2,\n            )\n        )\n    else:\n        for result in results:\n            print(f"{result.status.upper():7} {result.name}: {result.target} — {result.detail}")\n    return 1 if has_refresh_errors(results) else 0\n\n'''
if 'def _refresh_data(' not in text:
    if anchor not in text:
        raise SystemExit('CLI handler anchor not found')
    text = text.replace(anchor, handler + anchor, 1)

parser_anchor = '    stage_parser = subparsers.add_parser("run-stage")\n'
parser_block = '''    refresh_parser = subparsers.add_parser("refresh-data")\n    refresh_parser.add_argument("--repo-root", default=Path("."), type=Path)\n    refresh_parser.set_defaults(handler=_refresh_data)\n\n'''
if 'subparsers.add_parser("refresh-data")' not in text:
    if parser_anchor not in text:
        raise SystemExit('CLI parser anchor not found')
    text = text.replace(parser_anchor, parser_block + parser_anchor, 1)

p.write_text(text, encoding='utf-8', newline='\n')
print('wired refresh-data command into CLI')

from pathlib import Path

path = Path('uralla_build/preprocessor.py')
text = path.read_text(encoding='utf-8')

import_marker = 'from .errors import StageError\n'
import_line = 'from .area_pois import discover_marketplace_area_pois\n'
if import_line not in text:
    if import_marker not in text:
        raise SystemExit('import marker not found')
    text = text.replace(import_marker, import_line + import_marker, 1)

load_marker = '''    osmium = _load_osmium()\n    _emit_progress("POI context: indexing node signals in one pass")\n'''
load_replacement = '''    osmium = _load_osmium()\n    synthetic_area_pois = discover_marketplace_area_pois(str(source), osmium)\n    _emit_progress(\n        f"Area POI: marketplace candidates to synthesize: {len(synthetic_area_pois):,}"\n    )\n    _emit_progress("POI context: indexing node signals in one pass")\n'''
if load_marker not in text:
    raise SystemExit('osmium load marker not found')
text = text.replace(load_marker, load_replacement, 1)

writer_marker = '''                if final_tags == original_tags:\n                    writer.add(item)\n                else:\n                    writer.add(item.replace(tags=final_tags))\n\n        _progress(counters["objects_seen"], started)\n'''
writer_replacement = '''                if final_tags == original_tags:\n                    writer.add(item)\n                else:\n                    writer.add(item.replace(tags=final_tags))\n\n            for synthetic_index, synthetic in enumerate(synthetic_area_pois, start=1):\n                synthetic_decision = filter_tags(synthetic.tags, rules)\n                synthetic_tags, _ = enrich_long_name_tags(synthetic_decision.tags)\n                if synthetic_tags.get("amenity") != "marketplace":\n                    continue\n                synthetic_id = -(9_000_000_000_000_000 + synthetic_index)\n                writer.add_node(\n                    osmium.osm.mutable.Node(\n                        id=synthetic_id,\n                        location=osmium.osm.Location(synthetic.lon, synthetic.lat),\n                        tags=synthetic_tags,\n                    )\n                )\n                counters["synthetic_area_pois"] += 1\n                counters["synthetic_marketplace_pois"] += 1\n                _emit_progress(\n                    "[preprocess] area POI marketplace "\n                    f"{synthetic.source_type}{synthetic.source_id}: "\n                    f"{synthetic_tags.get('name')!r} -> node{synthetic_id} "\n                    f"({synthetic.lat:.6f}, {synthetic.lon:.6f})"\n                )\n\n        _progress(counters["objects_seen"], started)\n'''
if writer_marker not in text:
    raise SystemExit('writer tail marker not found')
text = text.replace(writer_marker, writer_replacement, 1)

path.write_text(text, encoding='utf-8')

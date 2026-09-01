from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:160]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"anchor not unique in {path}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Remove the legacy marketplace-only synthetic path from semantic preprocessing.
p = "uralla_build/preprocessor.py"
replace_once(p, "from .area_pois import discover_marketplace_area_pois\n", "")
replace_once(
    p,
    '''    synthetic_area_pois = discover_marketplace_area_pois(str(source), osmium)\n    _emit_progress(\n        f"Area POI: marketplace candidates to synthesize: {len(synthetic_area_pois):,}"\n    )\n''',
    "",
)
replace_once(
    p,
    '''            for synthetic_index, synthetic in enumerate(synthetic_area_pois, start=1):\n                synthetic_decision = filter_tags(synthetic.tags, rules)\n                synthetic_tags, _ = enrich_long_name_tags(synthetic_decision.tags)\n                if synthetic_tags.get("amenity") != "marketplace":\n                    continue\n                synthetic_id = -(9_000_000_000_000_000 + synthetic_index)\n                writer.add_node(\n                    osmium.osm.mutable.Node(\n                        id=synthetic_id,\n                        location=osmium.osm.Location(synthetic.lon, synthetic.lat),\n                        tags=synthetic_tags,\n                    )\n                )\n                counters["synthetic_area_pois"] += 1\n                counters["synthetic_marketplace_pois"] += 1\n                _emit_progress(\n                    "[preprocess] area POI marketplace "\n                    f"{synthetic.source_type}{synthetic.source_id}: "\n                    f"{synthetic_tags.get('name')!r} -> node{synthetic_id} "\n                    f"({synthetic.lat:.6f}, {synthetic.lon:.6f})"\n                )\n\n''',
    "",
)

# Area POIs become real input nodes before semantic/context enrichment, so synthetic
# objects participate in exactly the same H/M/L and naming logic as source nodes.
p = "uralla_build/preprocess_pipeline.py"
replace_once(
    p,
    '"""Composite preprocess entry: semantic enrichment, road density, then area POIs."""',
    '"""Composite preprocess entry: area POIs, semantic enrichment, then road density."""',
)
replace_once(
    p,
    '''    output = args.output.resolve()\n    semantic = output.parent / f".{output.name}.{uuid4().hex}.semantic.osm.pbf"\n    density = output.parent / f".{output.name}.{uuid4().hex}.road-density.osm.pbf"\n    try:\n        preprocess_pbf(\n            args.input,\n            semantic,\n            args.config,\n            args.profile,\n            args.report,\n        )\n        osmium = _load_osmium()\n        road_density_stats = augment_road_density(\n            semantic,\n            density,\n            osmium,\n            reporter=_report,\n        )\n        area_stats = augment_area_pois(\n            density,\n            output,\n            osmium,\n            reporter=_report,\n        )\n''',
    '''    output = args.output.resolve()\n    area = output.parent / f".{output.name}.{uuid4().hex}.area-pois.osm.pbf"\n    semantic = output.parent / f".{output.name}.{uuid4().hex}.semantic.osm.pbf"\n    try:\n        osmium = _load_osmium()\n        area_stats = augment_area_pois(\n            args.input,\n            area,\n            osmium,\n            reporter=_report,\n        )\n        preprocess_pbf(\n            area,\n            semantic,\n            args.config,\n            args.profile,\n            args.report,\n        )\n        road_density_stats = augment_road_density(\n            semantic,\n            output,\n            osmium,\n            reporter=_report,\n        )\n''',
)
replace_once(
    p,
    '''    finally:\n        if semantic.exists():\n            semantic.unlink()\n        if density.exists():\n            density.unlink()\n''',
    '''    finally:\n        if area.exists():\n            area.unlink()\n        if semantic.exists():\n            semantic.unlink()\n''',
)

# Make the area augmenter's role description match its new pipeline position.
p = "uralla_build/area_pois.py"
replace_once(
    p,
    '    """Copy a preprocessed PBF and prepend approved missing area-derived POIs."""\n',
    '    """Copy a source PBF and prepend approved missing area-derived POIs."""\n',
)

print("area POIs moved before semantic preprocessing")

from pathlib import Path

path = Path("uralla_build/preprocessor.py")
text = path.read_text(encoding="utf-8")

old = '''def _geographic_label_class(tags: Mapping[str, str]) -> str | None:\n    natural = tags.get("natural")\n'''
new = '''def _is_sanatorium_context(tags: Mapping[str, str]) -> bool:\n    if tags.get("healthcare") in {"sanatorium", "rehabilitation"}:\n        return True\n    if tags.get("amenity") in {"clinic", "hospital", "nursing_home"}:\n        return True\n    if tags.get("tourism") in {"hotel", "resort", "guest_house", "motel", "hostel"}:\n        return True\n    return tags.get("leisure") == "resort"\n\n\ndef _geographic_label_class(tags: Mapping[str, str]) -> str | None:\n    natural = tags.get("natural")\n'''
if old not in text:
    raise SystemExit("label-class anchor not found")
text = text.replace(old, new, 1)

old = '''    label = name.strip()\n    if result.get("ele"):\n'''
new = '''    label = name.strip()\n\n    # Compact the generic Russian facility type when the object's tags confirm\n    # a sanatorium / resort / accommodation / healthcare context.\n    sanatorium_match = re.fullmatch(r"\\s*санаторий\\s+(.+?)\\s*", label, re.IGNORECASE)\n    if sanatorium_match and _is_sanatorium_context(result):\n        tail = sanatorium_match.group(1).strip()\n        if tail:\n            label = "Сан. " + tail\n\n    if result.get("ele"):\n'''
if old not in text:
    raise SystemExit("label anchor not found")
text = text.replace(old, new, 1)

# Geographic cleanup historically returned early for non-natural objects. Allow\n# the sanatorium-specific display rule through the same label pipeline.
old = '''    if label_class is None and natural is None:\n        return result, False\n    name = result.get("name")\n'''
new = '''    if label_class is None and natural is None and not _is_sanatorium_context(result):\n        return result, False\n    name = result.get("name")\n'''
if old not in text:
    raise SystemExit("early-return anchor not found")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

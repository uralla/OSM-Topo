from pathlib import Path

path = Path("uralla_build/preprocessor.py")
text = path.read_text(encoding="utf-8")

old = '''def _geographic_label_class(tags: Mapping[str, str]) -> str | None:\n    natural = tags.get("natural")\n    if natural in PEAK_NATURAL_TYPES:\n        return "mountain"\n    if natural == "ridge":\n        return "ridge"\n    if natural == "waterfall":\n        return "waterfall"\n    water = tags.get("water")\n'''
new = '''def _geographic_label_class(tags: Mapping[str, str]) -> str | None:\n    natural = tags.get("natural")\n    if natural in PEAK_NATURAL_TYPES:\n        return "mountain"\n    if natural == "ridge":\n        return "ridge"\n    if natural == "waterfall":\n        return "waterfall"\n    if natural == "cave_entrance":\n        return "cave"\n    water = tags.get("water")\n'''
if old not in text:
    raise SystemExit("geographic label class pattern not found")
text = text.replace(old, new, 1)

old = '''    "waterfall": (\n        re.compile(r"^\\s*водопад\\s+(.+?)\\s*$", re.IGNORECASE),\n        re.compile(r"^\\s*вод(?:\\.\\s*|\\s+)(.+?)\\s*$", re.IGNORECASE),\n        re.compile(r"^\\s*вдп(?:\\.\\s*|\\s+)(.+?)\\s*$", re.IGNORECASE),\n    ),\n}\n'''
new = '''    "waterfall": (\n        re.compile(r"^\\s*водопад\\s+(.+?)\\s*$", re.IGNORECASE),\n        re.compile(r"^\\s*вод(?:\\.\\s*|\\s+)(.+?)\\s*$", re.IGNORECASE),\n        re.compile(r"^\\s*вдп(?:\\.\\s*|\\s+)(.+?)\\s*$", re.IGNORECASE),\n    ),\n    # Cave type words are normally written as a suffix in Russian OSM names.\n    # Strip only the trailing type marker; a leading "Пещера ..." may be an\n    # established proper name and is deliberately left untouched.\n    "cave": (\n        re.compile(r"^\\s*(.+?)\\s+пещера\\s*$", re.IGNORECASE),\n        re.compile(r"^\\s*(.+?)\\s+пещ(?:\\.|\\s*)$", re.IGNORECASE),\n    ),\n}\n'''
if old not in text:
    raise SystemExit("geographic prefix patterns block not found")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

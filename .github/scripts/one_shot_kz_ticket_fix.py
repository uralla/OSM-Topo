from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match, got {count}"
    return text.replace(old, new, 1)

# KZ is already a country extract, same as Crimea: do not run osmium extract again.
p = Path('config/maps.yaml')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    '  kz:\n    source: kazakhstan\n    polygon: poly/KZ.poly\n',
    '  kz:\n    source: kazakhstan\n    extract: false\n    polygon: poly/KZ.poly\n',
    'kz extract flag',
)
p.write_text(s, encoding='utf-8')

# 0x4c00 has FontStyle=NoLabel in the TYP, so a normal Garmin primary label is
# safe for hover/details without creating permanent map text.
p = Path('styles/uralla/inc/priority_points')
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    "shop=ticket & name=* { name '${name}' } [0x4c00 resolution 24]\nshop=ticket & name!=* { set mkgmap:label:1=' '; set mkgmap:label:2='билеты' } [0x4c00 resolution 24]\n",
    s_ticket := "shop=ticket { name '${name}' | 'билеты' } [0x4c00 resolution 24]\n",
    'ticket hover fallback',
)
p.write_text(s, encoding='utf-8')

# Keep the comment truthful.
p = Path('styles/uralla/inc/priority_points')
s = p.read_text(encoding='utf-8')
s = s.replace(
    '# Ticket shops use the information POI icon. Named objects keep their real name;\n# unnamed ones stay unlabeled on the map but expose "билеты" in object details/hover.\n' + s_ticket,
    '# Ticket shops use the information POI icon. 0x4c00 is NoLabel in the TYP, so\n# the primary Garmin label is available to hover/details without permanent map text.\n' + s_ticket,
    1,
)
p.write_text(s, encoding='utf-8')

# Direct invariants.
manifest = Path('config/maps.yaml').read_text(encoding='utf-8')
style = Path('styles/uralla/inc/priority_points').read_text(encoding='utf-8')
typ = Path('styles/uralla.txt').read_text(encoding='utf-8')
assert '  kz:\n    source: kazakhstan\n    extract: false\n' in manifest
assert "shop=ticket { name '${name}' | 'билеты' } [0x4c00 resolution 24]" in style
assert "mkgmap:label:2='билеты'" not in style
start = typ.index('[_point]\nType=0x04c\nSubType=0x00')
end = typ.index('[end]', start)
assert 'FontStyle=NoLabel (invisible)' in typ[start:end]

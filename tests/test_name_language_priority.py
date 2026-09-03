from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RULES = ROOT / "styles" / "uralla" / "inc" / "name"


def test_readable_name_priority_is_ru_then_latin_then_original():
    style = NAME_RULES.read_text(encoding="utf-8")

    semantic = "uralla:label=* { set name='${uralla:label}' }"
    russian = "uralla:label!=* & name:ru=* { set name='${name:ru}' }"
    english = "uralla:label!=* & name:ru!=* & name:en=* { set name='${name:en}' }"
    international = (
        "uralla:label!=* & name:ru!=* & name:en!=* & int_name=* "
        "{ set name='${int_name}' }"
    )
    latin = (
        "uralla:label!=* & name:ru!=* & name:en!=* & int_name!=* & name:latin=* "
        "{ set name='${name:latin}' }"
    )

    positions = [style.index(rule) for rule in (semantic, russian, english, international, latin)]
    assert positions == sorted(positions)
    assert "name=* { set name='${name|subst:" in style

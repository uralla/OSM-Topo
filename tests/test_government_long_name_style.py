from pathlib import Path


def test_government_long_name_fallback_precedes_normal_rule():
    text = Path("styles/uralla/points").read_text(encoding="utf-8")
    fallback = "office=government & uralla:long_name=yes { name 'учреждение' } [0x3003 resolution 24]"
    normal = "office=government [0x3003 resolution 24]"
    assert fallback in text
    assert normal in text
    assert text.index(fallback) < text.index(normal)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLYGONS = ROOT / "styles" / "uralla" / "polygons"
TYP = ROOT / "styles" / "uralla.txt"

def test_polygon_label_collision_fixes_are_present():
    style = POLYGONS.read_text(encoding="utf-8")
    typ = TYP.read_text(encoding="utf-8")
    area = style[style.index("# squares and plazas"):style.index("# ж/д платформы как площади")]
    assert "0x10f12 resolution 21" in area
    assert "0x0d resolution 21" not in area
    assert "String1=0x19,пешеходная зона" in typ
    assert "Type=0x10f12" in typ
    assert "String1=0x19,здание" in typ
    for place in ("town", "city", "suburb", "village", "hamlet", "locality", "isolated_dwelling"):
        assert f"place={place} & building!=*" in style

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLYGONS = ROOT / "styles" / "uralla" / "polygons"
TYP = ROOT / "styles" / "uralla.txt"

def test_unnamed_building_has_explicit_hover_fallback():
    style = POLYGONS.read_text(encoding="utf-8")
    assert "building=* \t{name '${name}' | '${addr:street} ${addr:housenumber}' | '${addr:housenumber}' | 'здание' } [0x13 resolution 24]" in style
    assert "String1=0x19,здание" in TYP.read_text(encoding="utf-8")

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDUSE = ROOT / "styles" / "uralla" / "inc" / "landuse_polygons"


def test_forest_has_no_medium_zoom_gap():
    style = LANDUSE.read_text(encoding="utf-8")

    assert "natural=wood [0x1321e resolution 19-21 continue]" in style
    assert "natural=wood [0x1321e resolution 22-23 continue]" in style
    assert (
        "natural=wood & (leaf_type=needleleaved | wood=coniferous) "
        "[0x1321f resolution 22-23 continue]"
    ) not in style
    assert "natural=wood [0x50 resolution 24]" in style


def test_forest_medium_zoom_fallback_precedes_resolution_24_rules():
    style = LANDUSE.read_text(encoding="utf-8")

    fallback = style.index("natural=wood [0x1321e resolution 22-23 continue]")
    detail = style.index("natural=wood & leaf_type=needleleaved [0x10100 resolution 24]")

    assert fallback < detail

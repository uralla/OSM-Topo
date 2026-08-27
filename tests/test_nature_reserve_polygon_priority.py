from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLYGONS = (ROOT / "styles" / "uralla" / "polygons").read_text(encoding="utf-8")
LANDUSE = (ROOT / "styles" / "uralla" / "inc" / "landuse_polygons").read_text(encoding="utf-8")


def test_modern_protected_area_boundary_owns_overview_fill_once():
    modern = (
        "(boundary=protected_area | boundary=national_park) & area_size()>50000 "
        "[0x16 resolution 19-22 continue]"
    )
    assert modern in LANDUSE

    assert (
        "(leisure=nature_reserve | leisure=natural_reserve | "
        "landuse=nature_reserve | landuse=natural_reserve)"
    ) in POLYGONS
    assert "boundary!=protected_area & boundary!=national_park" in POLYGONS

    old = (
        "leisure=nature_reserve & area_size()>50000 | "
        "leisure=natural_reserve & area_size()>50000 | "
        "landuse=nature_reserve & area_size()>50000 | "
        "landuse=natural_reserve & area_size()>50000 "
        "[0x16 resolution 19-22 continue]"
    )
    assert old not in POLYGONS

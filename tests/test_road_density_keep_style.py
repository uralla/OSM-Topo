from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla" / "inc" / "road_density"


def _style() -> str:
    return STYLE.read_text(encoding="utf-8")


def test_keep_minor_and_unclassified_bypass_length_gates() -> None:
    text = _style()

    assert "highway=minor & uralla:road_density=keep [0x06 resolution 20-22 continue]" in text
    assert "highway=unclassified & uralla:road_density=keep [0x07 resolution 19-21 continue]" in text
    assert "highway=minor & uralla:road_density=keep & length()>" not in text
    assert "highway=unclassified & uralla:road_density=keep & length()>" not in text


def test_keep_residential_and_service_preserve_normal_overview_lod() -> None:
    text = _style()

    assert (
        "highway=residential & area!=yes & uralla:road_density=keep "
        "[0x07 resolution 22-22 continue]"
    ) in text
    assert (
        "highway=service & service!=alley & service!=driveway & oneway!=yes "
        "& uralla:road_density=keep [0x07 resolution 23-23 continue]"
    ) in text


def test_dense_suppression_length_thresholds_remain_in_place() -> None:
    text = _style()

    assert "highway=minor & uralla:road_density=dense & length()>400" in text
    assert "highway=unclassified & uralla:road_density=dense & length()>500" in text
    assert "highway=track & tracktype!=grade1 & uralla:road_density=dense & length()>100" in text

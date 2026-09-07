from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATER = ROOT / "styles" / "uralla" / "inc" / "water_lines"
ARGS = ROOT / "styles" / "uralla.args"


def test_water_flow_arrows_use_original_0x0f_carrier() -> None:
    text = WATER.read_text(encoding="utf-8")

    assert "[0x10f11 resolution 24 continue]" not in text
    assert "[0x0f road_class=0 road_speed=0 resolution 24 continue]" in text
    assert "add access=no; add taxi=yes; set oneway=yes" in text


def test_0x0f_carrier_covers_rivers_streams_and_related_waterways() -> None:
    text = WATER.read_text(encoding="utf-8")

    start = text.index("(waterway=canal")
    end = text.index("###\n", start)
    carrier = text[start:end]

    for selector in (
        "waterway=river",
        "waterway=stream",
        "waterway=drain",
        "waterway=canal",
        "waterway=rapid",
        "waterway=rapids",
        "whitewater=rapid",
        "whitewater=rapids",
    ):
        assert selector in carrier
    assert "tunnel!=*" in carrier


def test_0x0f_carrier_precedes_water_visual_ownership() -> None:
    text = WATER.read_text(encoding="utf-8")

    arrow = text.index("[0x0f road_class=0 road_speed=0 resolution 24 continue]")
    river = text.index("uralla:river_rank=*")
    intermittent = text.index("waterway=stream & intermittent=yes")
    stream = text.index("waterway=stream & intermittent!=yes")

    assert arrow < river
    assert arrow < intermittent
    assert arrow < stream


def test_reverse_merge_cannot_flip_0x0f_water_carrier() -> None:
    text = ARGS.read_text(encoding="utf-8")
    assert "allow-reverse-merge" in text
    assert "line-types-with-direction=0x0f" in text
    assert "line-types-with-direction=0x10f11" not in text

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATER = ROOT / "styles" / "uralla" / "inc" / "water_lines"
TYP = ROOT / "styles" / "uralla.txt"


def _line_block(text: str, type_code: str) -> str:
    marker = f"[_line]\nType={type_code}\n"
    start = text.index(marker)
    end = text.index("[end]", start)
    return text[start:end]


def test_water_flow_arrows_use_non_routable_directional_overlay() -> None:
    text = WATER.read_text(encoding="utf-8")

    arrow_rule = "(waterway=river | waterway=stream | waterway=drain | waterway=canal)\n & area!=yes & tunnel!=yes [0x10f11 resolution 24 continue]"
    assert arrow_rule in text
    assert "[0x0f road_class=" not in text
    assert "[0x0f road_speed=" not in text


def test_direction_overlay_precedes_water_visual_ownership() -> None:
    text = WATER.read_text(encoding="utf-8")

    arrow = text.index("[0x10f11 resolution 24 continue]")
    river = text.index("uralla:river_rank=1")
    intermittent = text.index("(waterway=stream | waterway=drain) & intermittent=yes")
    stream = text.index("waterway=stream & intermittent!=yes")

    assert arrow < river
    assert arrow < intermittent
    assert arrow < stream


def test_typ_direction_overlay_is_non_routable_and_oriented() -> None:
    text = TYP.read_text(encoding="utf-8")
    block = _line_block(text, "0x10f11")

    assert "Non-routable customizable line" in block
    assert "UseOrientation=Y" in block

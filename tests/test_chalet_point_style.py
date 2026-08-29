from pathlib import Path
import re


POINTS = Path("styles/uralla/points")
TYP = Path("styles/uralla.txt")


def test_chalet_uses_dedicated_custom_poi_type():
    text = POINTS.read_text()
    assert "tourism=chalet [0x640d resolution 21]" in text
    assert "tourism=chalet [0x2b02 resolution 21]" not in text


def test_chalet_typ_block_has_correct_semantics():
    typ = TYP.read_text()
    match = re.search(
        r"\[_point\]\nType=0x02b\nSubType=0x08\n.*?\n\[end\]",
        typ,
        re.S,
    )
    assert match
    block = match.group(0)
    assert "String1=0x19,коттедж" in block
    assert "String2=0x04,chalet" in block

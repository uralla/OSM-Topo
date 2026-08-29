from pathlib import Path


def test_beekeeper_uses_safe_poi_type():
    points = Path('styles/uralla/points').read_text()
    assert 'craft=beekeeper [0x2f1a resolution 24]' in points
    assert 'craft=beekeeper [0x11505 resolution 24]' not in points


def test_beekeeper_typ_moved_from_extended_type():
    typ = Path('styles/uralla.txt').read_text()
    assert '[_point]\nType=0x02f\nSubType=0x1a\n' in typ
    assert '[_point]\nType=0x115\nSubType=0x05\n' not in typ

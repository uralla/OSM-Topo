from pathlib import Path


def test_fire_station_uses_safe_poi_type():
    points = Path('styles/uralla/points').read_text(encoding='utf-8')
    typ = Path('styles/uralla.txt').read_text(encoding='utf-8')

    assert 'amenity=fire_station [0x3008 resolution 24]' in points
    assert 'amenity=fire_station [0x11503 resolution 24]' not in points
    assert 'Type=0x030\nSubType=0x08' in typ
    assert 'Type=0x115\nSubType=0x03' not in typ

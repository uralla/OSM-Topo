from pathlib import Path


def test_admin_service_long_name_fallbacks():
    points = Path("styles/uralla/points").read_text(encoding="utf-8")
    expected = [
        "amenity=townhall & uralla:long_name=yes { name 'администрация' } [0x3003 resolution 24]",
        "amenity=library & uralla:long_name=yes { name 'библиотека' } [0x2c03 resolution 24]",
        "amenity=police & uralla:long_name=yes { name 'полиция' } [0x3001 resolution 23]",
        "amenity=post_office & uralla:long_name=yes { name 'почта' } [0x2f05 resolution 24]",
        "amenity=fire_station & uralla:long_name=yes { name 'пожарная часть' } [0x3008 resolution 24]",
    ]
    for rule in expected:
        assert rule in points

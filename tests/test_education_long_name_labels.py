from pathlib import Path


def test_education_long_name_fallbacks_precede_normal_rules():
    text = Path('styles/uralla/points').read_text(encoding='utf-8')
    pairs = [
        ("amenity=college & uralla:long_name=yes { name 'колледж' } [0x2c05 resolution 24]", "amenity=college [0x2c05 resolution 24]"),
        ("amenity=kindergarten & uralla:long_name=yes { name 'детский сад' } [0x2c05 resolution 24]", "amenity=kindergarten [0x2c05 resolution 24]"),
        ("amenity=school & uralla:long_name=yes { name 'школа' } [0x2c05 resolution 24]", "amenity=school [0x2c05 resolution 24]"),
        ("amenity=university & uralla:long_name=yes { name 'университет' } [0x2c05 resolution 24]", "amenity=university [0x2c05 resolution 24]"),
    ]
    for fallback, normal in pairs:
        assert fallback in text
        assert normal in text
        assert text.index(fallback) < text.index(normal)

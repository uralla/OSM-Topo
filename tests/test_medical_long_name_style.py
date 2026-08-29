from pathlib import Path


def test_medical_long_name_fallbacks_precede_generic_rules():
    text = Path('styles/uralla/points').read_text(encoding='utf-8')
    pairs = [
        ("amenity=hospital & uralla:long_name=yes { name 'больница' } [0x3002 resolution 24]", "healthcare=hospital | amenity=hospital | amenity=clinic [0x3002 resolution 24]"),
        ("amenity=clinic & uralla:long_name=yes { name 'клиника' } [0x3002 resolution 24]", "healthcare=hospital | amenity=hospital | amenity=clinic [0x3002 resolution 24]"),
        ("amenity=doctors & uralla:long_name=yes { name 'поликлиника' } [0x3002 resolution 24]", "healthcare=* | amenity=doctors [0x3002 resolution 24]"),
        ("amenity=dentist & uralla:long_name=yes { name 'стоматология' } [0x3010 resolution 24]", "amenity=dentist [0x3010 resolution 24]"),
    ]
    for specific, generic in pairs:
        assert specific in text
        assert generic in text
        assert text.index(specific) < text.index(generic)


def test_healthcare_catchall_has_no_long_name_fallback():
    text = Path('styles/uralla/points').read_text(encoding='utf-8')
    assert "healthcare=* & uralla:long_name=yes" not in text

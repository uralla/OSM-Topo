from pathlib import Path

from uralla_build.river_landmarks import load_river_landmarks, normalize_river_name


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog/river-landmarks.tsv"


def test_eurasian_long_river_catalogue_has_geographic_coverage():
    rivers = load_river_landmarks(CATALOG)

    expected = {
        # East and Southeast Asia.
        "Yangtze": 1,
        "Yellow River": 1,
        "Mekong": 1,
        "Pearl River": 2,
        "Songhua River": 2,
        # South and Central Asia.
        "Indus": 1,
        "Ganges": 2,
        "Brahmaputra": 2,
        "Amu Darya": 2,
        "Syr Darya": 2,
        # Siberia and the Far East.
        "Lena": 1,
        "Yenisei": 1,
        "Lower Tunguska": 2,
        "Amur": 1,
        "Argun": 2,
        # Europe.
        "Volga": 1,
        "Danube": 2,
        "Dnieper": 2,
        "Don": 2,
        "Rhine": 3,
    }

    for name, rank in expected.items():
        assert rivers[normalize_river_name(name)] == rank

from pathlib import Path

from uralla_build.preprocessor import load_peak_landmarks


ROOT = Path(__file__).resolve().parents[1]
PEAK_CATALOG = ROOT / "catalog" / "peak-landmarks.tsv"


def test_eurasia_landmark_catalog_keeps_regional_anchors() -> None:
    landmarks = load_peak_landmarks(PEAK_CATALOG)

    expected = {
        # Crimea
        "Q2092607",  # Roman-Kosh
        "Q1517833",  # Ai-Petri
        # Europe
        "Q203942",  # Galdhøpiggen
        "Q627508",  # Hoverla
        # Caucasus / West Asia
        "Q217457",  # Shkhara
        "Q203568",  # Aragats
        # Central Asia
        "Q332762",  # Jengish Chokusu
        "Q41413",  # Ismoil Somoni Peak
        # Himalaya / Tibet
        "Q130736",  # Nanga Parbat
        "Q229107",  # Kailash
        # Siberia / Far East
        "Q392246",  # Munku-Sardyk
        "Q1092160",  # Tordoki Yani
        # East / Southeast Asia
        "Q107635",  # Baekdu / Paektu
        "Q500275",  # Yushan
        "Q123782",  # Fansipan
    }

    assert expected <= landmarks
    assert len(landmarks) >= 60

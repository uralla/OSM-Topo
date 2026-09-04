from pathlib import Path

from uralla_build.preprocessor import (
    DISPLAY_LABEL_TAG,
    PEAK_LANDMARK_TAG,
    enrich_geographic_label_tags,
    enrich_peak_landmark_tags,
    load_peak_landmarks,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "peak-landmarks.tsv"
PENDING = ROOT / "catalog" / "peak-landmarks.pending.tsv"


def test_confirmed_legacy_peak_qids_are_in_catalog() -> None:
    landmarks = load_peak_landmarks(CATALOG)

    assert {
        "Q2669289",  # Большой Иремель
        "Q4429818",  # Сосьвинский Камень
        "Q2709826",  # Денежкин Камень
        "Q4339903",  # Отортен
        "Q4342241",  # Пай-Ер / Пайер
    } <= landmarks


def test_bolshoy_iremel_is_marked_before_geographic_name_compaction() -> None:
    landmarks = load_peak_landmarks(CATALOG)
    tags, changed = enrich_peak_landmark_tags(
        {
            "natural": "peak",
            "name": "Большой Иремель",
            "wikidata": "Q2669289",
            "ele": "1582",
        },
        landmarks,
    )

    assert changed is True
    assert tags[PEAK_LANDMARK_TAG] == "yes"

    labeled, _ = enrich_geographic_label_tags(tags)
    assert labeled.get(DISPLAY_LABEL_TAG, labeled["name"]) == "Большой Иремель"
    assert labeled.get(DISPLAY_LABEL_TAG) != "Бол. Иремель"


def test_unconfirmed_hardcoded_peak_names_remain_explicitly_tracked() -> None:
    names = {
        line.strip()
        for line in PENDING.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#") and line.strip() != "name"
    }

    assert names == {
        "пик Меридиан",
        "Кожимзиз",
        "Толпоз-Из",
        "Неройка",
        "Сабля",
        "Райиз",
    }


def test_every_hardcoded_peak_anchor_is_in_catalog_or_pending_inventory() -> None:
    catalog_text = CATALOG.read_text(encoding="utf-8")
    pending_text = PENDING.read_text(encoding="utf-8")
    inventory = catalog_text + "\n" + pending_text

    hardcoded_names = {
        "Ослянка",
        "Конжаковский Камень",
        "Большой Иремель",
        "Ямантау",
        "Эльбрус Западный",
        "Фишт",
        "Казбек",
        "Юдычвумчорр",
        "Белуха",
        "пик Семенова-Тян-Шанского",
        "Талғар шыңы",
        "Чок-Тал",
        "пик Меридиан",
        "Данков чокусу",
        "Хан Тәңірі - Хан-Теңири - 汗腾格里峰",
        "Сосьвинский",
        "Денежкин Камень",
        "Отортен",
        "Кожимзиз",
        "Толпоз-Из",
        "Неройка",
        "Сабля",
        "Манарага",
        "Пай-Ер",
        "Mount Ararat",
        "Райиз",
    }

    missing = sorted(name for name in hardcoded_names if name not in inventory)
    assert missing == []

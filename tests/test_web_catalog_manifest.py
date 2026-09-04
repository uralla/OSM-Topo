from copy import deepcopy
from pathlib import Path

from uralla_build.manifest import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]


CANONICAL_WEB_CATALOG = {
    "Topo-Ural-S.img": "Урал (южная часть)",
    "Topo-Ural-N.img": "Урал (северная часть)",
    "Ural-fed-district.img": "Уральский федеральный округ",
    "Volga-fed-district.img": "Приволжский федеральный округ",
    "North-Caucasus.OSM.img": "Северокавказский федеральный округ",
    "Central-fed-district.img": "Центральный федеральный округ",
    "South-fed-district.img": "Южный федеральный округ",
    "Northwestern-fed-district.img": "Северо-Западный федеральный округ",
    "topo-irk.img": "Иркутская область",
    "topo-zap-sib.img": "Западная Сибирь",
    "topo-sa-e.img": "Якутия (восток)",
    "topo-sa-w.img": "Якутия (запад)",
    "topo-mag.img": "Магаданская область",
    "topo-kya-s.img": "Красноярский край (юг)",
    "topo-kya-n.img": "Красноярский край (север)",
    "topo-sak.img": "Сахалин и острова",
    "topo-bu-zab-amu.img": "Бурятия, Забайкалье, Амурская область",
    "topo-chu-kam.img": "Чукотка, Камчатка и острова",
    "topo-pri-kha-yev.img": "Приморский и Хабаровский край, Еврейский АО",
    "Belarus.OSM.img": "Беларусь",
    "Crimea.OSM.img": "Крым",
    "KG.OSM.img": "Киргизия",
    "KZ.OSM.img": "Казахстан",
    "Georgia.OSM.img": "Грузия",
    "Armenia.OSM.img": "Армения",
    "Turkey.OSM.img": "Турция",
    "Mongolia.OSM.img": "Монголия",
}


def test_real_manifest_web_catalog_matches_canonical_public_set():
    manifest = load_manifest(ROOT / "config" / "maps.yaml")
    issues = validate_manifest(manifest)
    assert not issues

    products = manifest["products"]
    visible_products = [
        product
        for product in products.values()
        if product.get("web", {}).get("visible") is True
    ]

    assert len(products) == 27
    assert len(visible_products) == 27

    actual = {
        product["names"]["output_img"]: product["web"]["title"]
        for product in visible_products
    }
    assert actual == CANONICAL_WEB_CATALOG


def test_family_ids_and_reserved_map_ranges_are_unique():
    manifest = load_manifest(ROOT / "config" / "maps.yaml")
    products = manifest["products"]

    family_ids = [product["identity"]["family_id"] for product in products.values()]
    assert len(family_ids) == len(set(family_ids))

    ranges = []
    for key, product in products.items():
        identity = product["identity"]
        start = int(identity["overview_mapnumber"])
        end = int(identity["last_reserved_mapid"])
        ranges.append((start, end, key))

    ranges.sort()
    for (_, prev_end, prev_key), (next_start, _, next_key) in zip(ranges, ranges[1:]):
        assert prev_end < next_start, f"map-id ranges overlap: {prev_key} and {next_key}"


def test_ural_n_keeps_collision_free_reassigned_family_id():
    manifest = load_manifest(ROOT / "config" / "maps.yaml")
    identity = manifest["products"]["ural-n"]["identity"]
    assert identity["family_id"] == 1027
    assert identity["overview_mapnumber"] == "01027000"
    assert identity["first_tile_mapid"] == "01027001"
    assert identity["last_reserved_mapid"] == "01027999"


def test_visible_web_product_requires_title():
    manifest = load_manifest(ROOT / "config" / "maps.yaml")
    broken = deepcopy(manifest)
    broken["products"]["ural-s"]["web"] = {"visible": True, "order": 10}

    issues = validate_manifest(broken)

    assert any(
        issue.location == "products.ural-s.web.title"
        and "required" in issue.message
        for issue in issues
    )


def test_web_order_and_visible_types_are_validated():
    manifest = load_manifest(ROOT / "config" / "maps.yaml")
    broken = deepcopy(manifest)
    broken["products"]["ural-s"]["web"]["visible"] = "yes"
    broken["products"]["ural-s"]["web"]["order"] = -1

    issues = validate_manifest(broken)

    locations = {issue.location for issue in issues}
    assert "products.ural-s.web.visible" in locations
    assert "products.ural-s.web.order" in locations

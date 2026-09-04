from copy import deepcopy
from pathlib import Path

from uralla_build.manifest import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_real_manifest_web_catalog_is_valid_and_opt_in():
    manifest = load_manifest(ROOT / "config" / "maps.yaml")
    issues = validate_manifest(manifest)
    assert not issues

    products = manifest["products"]
    visible = [
        key
        for key, product in products.items()
        if product.get("web", {}).get("visible") is True
    ]
    assert len(visible) == 24
    assert products["ural-s"]["web"] == {
        "title": "Урал (южная часть)",
        "order": 10,
        "visible": True,
    }
    assert products["kz"]["web"]["title"] == "Казахстан"
    assert products["sfo"]["web"] == {"visible": False}
    assert products["yamal"]["web"] == {"visible": False}
    assert products["yakutia"]["web"] == {"visible": False}
    assert products["yugra"]["web"] == {"visible": False}


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

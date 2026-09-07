from pathlib import Path

from uralla_build.manifest import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "maps.yaml"


def test_test_product_matches_ural_s_build_profile_with_own_identity() -> None:
    manifest = load_manifest(MANIFEST)
    products = manifest["products"]
    assert "test" in products

    test = products["test"]
    ural_s = products["ural-s"]

    assert test["source"] == ural_s["source"] == "russia"
    assert test["preprocess_mode"] == ural_s["preprocess_mode"] == "fast"
    assert test["preprocess_workers"] == ural_s["preprocess_workers"] == 2
    assert test["elevation"] == ural_s["elevation"] == "elevation/ural.osm.pbf"
    assert test["geonames"] == ural_s["geonames"] == "input/cities15000.zip"
    assert test["splitter"] == ural_s["splitter"]
    assert test["mkgmap"] == ural_s["mkgmap"]

    assert test["polygon"] == "poly/test.poly"
    assert (ROOT / test["polygon"]).is_file()

    assert test["identity"] == {
        "family_id": 1028,
        "product_id": 1,
        "overview_mapnumber": "01028000",
        "first_tile_mapid": "01028001",
        "last_reserved_mapid": "01028999",
    }
    assert test["names"] == {
        "family": "TEST",
        "series": "TEST",
        "overview": "TEST",
        "description": "TEST",
        "output_img": "TEST.img",
    }
    assert test["web"]["title"] == "TEST"
    assert test["web"]["visible"] is True


def test_manifest_stays_valid_with_test_product() -> None:
    manifest = load_manifest(MANIFEST)
    assert validate_manifest(manifest) == []

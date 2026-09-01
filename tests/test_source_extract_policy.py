from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def test_complete_geofabrik_products_skip_extract():
    manifest = yaml.safe_load((ROOT / "config/maps.yaml").read_text(encoding="utf-8"))
    products = manifest["products"]
    expected = {
        "armenia": "armenia", "belarus": "belarus", "crimea": "crimea",
        "georgia": "georgia", "kg": "kyrgyzstan", "kz": "kazakhstan",
        "mongolia": "mongolia", "northwestern-fed-district": "northwestern",
        "turkey": "turkey",
    }
    for product, source in expected.items():
        assert products[product]["source"] == source
        assert products[product].get("extract") is False

def test_all_manifest_sources_have_download_urls():
    from uralla_build.external_data import OSM_SOURCE_URLS
    manifest = yaml.safe_load((ROOT / "config/maps.yaml").read_text(encoding="utf-8"))
    assert set(manifest["sources"]) == set(OSM_SOURCE_URLS)

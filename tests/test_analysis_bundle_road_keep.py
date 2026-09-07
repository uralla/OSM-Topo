from unittest.mock import patch

from uralla_build.analysis_bundle import _load_road_hints


def test_fast_analysis_bundle_keeps_backbone_hints() -> None:
    payload = {
        "ways": {
            "101": ["minor", "keep"],
            "102": ["minor", "dense"],
            "103": ["track", "very_dense"],
            "104": ["track", "ignored"],
        }
    }

    with patch("uralla_build.analysis_bundle.load_road_density_analysis", return_value=payload):
        hints = _load_road_hints("unused.json.gz")

    assert hints == {
        101: ("minor", "keep"),
        102: ("minor", "dense"),
        103: ("track", "very_dense"),
    }

from pathlib import Path

from uralla_build.poi_context_analysis import SCHEMA_VERSION
from uralla_build.settlement_lod import SettlementCandidate, rank_settlement_candidates


ROOT = Path(__file__).resolve().parents[1]
PLACE_STYLE = ROOT / "styles" / "uralla" / "inc" / "place_points"
MAP_RECIPE = ROOT / "uralla_build" / "map_recipe.py"


def _candidate(
    osm_id: int,
    place: str,
    *,
    population: int = 0,
    lat: float = 54.0,
    lon: float = 58.0,
) -> SettlementCandidate:
    return SettlementCandidate(osm_id, lat, lon, place, population)


def test_village_outranks_nearby_locality_even_if_locality_has_population() -> None:
    lods, _ = rank_settlement_candidates(
        [
            _candidate(100, "village", population=0),
            _candidate(200, "locality", population=5000, lon=58.01),
        ]
    )

    assert lods[100] == 19
    assert lods[200] == 21


def test_hamlet_outranks_equal_bottom_tier() -> None:
    lods, _ = rank_settlement_candidates(
        [
            _candidate(100, "hamlet"),
            _candidate(200, "farm", population=9999, lon=58.01),
            _candidate(300, "isolated_dwelling", lon=58.02),
            _candidate(400, "locality", lon=58.03),
        ]
    )

    assert lods[100] == 19
    assert lods[200] >= 20
    assert lods[300] >= 20
    assert lods[400] >= 20


def test_bottom_tier_is_equal_and_population_breaks_priority() -> None:
    lods, _ = rank_settlement_candidates(
        [
            _candidate(100, "locality", population=50),
            _candidate(200, "farm", population=500, lon=58.01),
            _candidate(300, "isolated_dwelling", population=5, lon=58.02),
        ]
    )

    assert lods[200] == 21
    assert lods[100] == 21
    assert lods[300] == 21


def test_remote_low_priority_anchor_never_goes_farther_than_21() -> None:
    lods, _ = rank_settlement_candidates(
        [
            _candidate(100, "village", lat=54.0, lon=58.0),
            _candidate(200, "locality", lat=55.0, lon=60.0),
        ]
    )

    assert lods[100] == 19
    assert lods[200] == 21


def test_place_style_uses_dedicated_settlement_lod_not_generic_screen_pressure() -> None:
    text = PLACE_STYLE.read_text(encoding="utf-8")

    assert "uralla:poi_screen_pressure=" not in text
    assert "place=village & mkgmap:area2poi!=true & uralla:settlement_lod=19" in text
    assert "place=hamlet & mkgmap:area2poi!=true & uralla:settlement_lod=19" in text
    assert "place=locality & name=* & mkgmap:area2poi!=true & uralla:settlement_lod=19 { name '${name}' } [0x6408 resolution 21]" in text


def test_analysis_cache_and_recipe_track_settlement_algorithm() -> None:
    recipe = MAP_RECIPE.read_text(encoding="utf-8")

    assert SCHEMA_VERSION == 5
    assert '"uralla_build/settlement_lod.py"' in recipe

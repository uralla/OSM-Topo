from uralla_build.road_density_analysis import (
    BACKBONE_MAX_WAYS,
    SCHEMA_VERSION,
    _select_connected_backbone,
)


def candidate(rank: float, way_id: int, *nodes: int):
    return ((rank, 0, rank, -way_id), way_id, frozenset(nodes))


def test_backbone_keeps_connected_split_road_chain():
    candidates = [
        candidate(9.0, 101, 1, 2),
        candidate(10.0, 102, 2, 3),
        candidate(8.0, 103, 3, 4),
    ]

    assert _select_connected_backbone(candidates) == {101, 102, 103}


def test_backbone_does_not_keep_disconnected_high_rank_stub():
    candidates = [
        candidate(10.0, 201, 10, 11),
        candidate(9.0, 202, 11, 12),
        candidate(100.0, 299, 90, 91),
    ]

    # The highest-ranked way is the seed by design. A disconnected component-like
    # candidate cannot pull unrelated ways into the same kept chain.
    assert _select_connected_backbone(candidates, limit=2) == {299}


def test_backbone_is_deliberately_small():
    candidates = [
        candidate(10.0, 301, 1, 2),
        candidate(9.0, 302, 2, 3),
        candidate(8.0, 303, 3, 4),
        candidate(7.0, 304, 4, 5),
    ]

    kept = _select_connected_backbone(candidates)
    assert len(kept) == BACKBONE_MAX_WAYS == 3
    assert kept == {301, 302, 303}


def test_backbone_semantics_invalidate_old_analysis_cache():
    assert SCHEMA_VERSION == 4

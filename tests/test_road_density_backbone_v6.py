from uralla_build.road_density_analysis import (
    _BackboneCandidate,
    _Endpoint,
    _select_connected_backbone,
)


def _candidate(
    way_id: int,
    render_class: str,
    start: int,
    end: int,
    start_vec: tuple[float, float],
    end_vec: tuple[float, float],
    *,
    name: str = "",
    ref: str = "",
    rank_length: float = 100.0,
) -> _BackboneCandidate:
    return _BackboneCandidate(
        way_id=way_id,
        render_class=render_class,
        name=name,
        ref=ref,
        rank=(rank_length, int(bool(name)), rank_length, -way_id),
        endpoints=(
            _Endpoint(start, *start_vec),
            _Endpoint(end, *end_vec),
        ),
    )


def test_backbone_continues_straight_through_t_junction() -> None:
    # 1 arrives at node 20 from the west. Way 2 continues east, while way 3
    # branches north. The overview trunk must not hang at the junction.
    candidates = {
        1: _candidate(1, "track", 10, 20, (1.0, 0.0), (-1.0, 0.0)),
        2: _candidate(2, "track", 20, 30, (1.0, 0.0), (-1.0, 0.0)),
        3: _candidate(3, "track", 20, 40, (0.0, 1.0), (0.0, -1.0)),
    }

    assert _select_connected_backbone(candidates, 1) == {1, 2}


def test_backbone_prefers_matching_ref_before_straightness() -> None:
    candidates = {
        1: _candidate(1, "track", 10, 20, (1.0, 0.0), (-1.0, 0.0), ref="A"),
        # Geometrically straight but different road identity.
        2: _candidate(2, "track", 20, 30, (1.0, 0.0), (-1.0, 0.0), ref="B"),
        # Turns, but continues the same referenced road.
        3: _candidate(3, "track", 20, 40, (0.0, 1.0), (0.0, -1.0), ref="A"),
    }

    assert _select_connected_backbone(candidates, 1) == {1, 3}


def test_backbone_can_cross_low_road_class_transition() -> None:
    # Density is still calculated independently by class, but a visually
    # continuous trunk may continue across an OSM class change.
    candidates = {
        1: _candidate(1, "track", 10, 20, (1.0, 0.0), (-1.0, 0.0), name="Forest road"),
        2: _candidate(2, "unclassified", 20, 30, (1.0, 0.0), (-1.0, 0.0), name="Forest road"),
        3: _candidate(3, "service", 20, 40, (0.0, 1.0), (0.0, -1.0)),
    }

    assert _select_connected_backbone(candidates, 1) == {1, 2}


def test_backbone_keeps_only_one_branch() -> None:
    candidates = {
        1: _candidate(1, "track", 10, 20, (1.0, 0.0), (-1.0, 0.0)),
        2: _candidate(2, "track", 20, 30, (1.0, 0.0), (-1.0, 0.0)),
        3: _candidate(3, "track", 20, 40, (0.0, 1.0), (0.0, -1.0)),
        4: _candidate(4, "track", 20, 50, (0.0, -1.0), (0.0, 1.0)),
    }

    keep = _select_connected_backbone(candidates, 1)
    assert 1 in keep
    assert len(keep & {2, 3, 4}) == 1
    assert 2 in keep

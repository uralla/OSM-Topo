from uralla_build.area_pois import interior_point, point_in_polygon


def test_interior_point_stays_inside_l_shaped_polygon():
    ring = [
        (0.0, 0.0),
        (4.0, 0.0),
        (4.0, 1.0),
        (1.0, 1.0),
        (1.0, 4.0),
        (0.0, 4.0),
        (0.0, 0.0),
    ]
    point = interior_point(ring)
    assert point is not None
    assert point_in_polygon(point, ring)
    # The bounding-box centre (2,2) is outside this L shape; our point must not be it.
    assert point != (2.0, 2.0)


def test_point_in_polygon_rejects_l_shape_hole_like_corner():
    ring = [
        (0.0, 0.0),
        (4.0, 0.0),
        (4.0, 1.0),
        (1.0, 1.0),
        (1.0, 4.0),
        (0.0, 4.0),
        (0.0, 0.0),
    ]
    assert point_in_polygon((0.5, 3.0), ring)
    assert not point_in_polygon((2.0, 2.0), ring)

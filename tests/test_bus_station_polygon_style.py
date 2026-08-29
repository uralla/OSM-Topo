from pathlib import Path


def test_bus_station_does_not_use_parking_polygon_type():
    polygons = Path("styles/uralla/polygons").read_text()
    assert "amenity=bus_station [0x05" not in polygons
    assert "amenity=parking | parking=surface [0x05 resolution 24]" in polygons

import pytest

from app.geo import multipolygon_area_km2, polygon_area_km2

# A roughly 1km x 1km square near Kathmandu (27.7N, 85.3E), where
# 1 degree longitude ≈ 111.32 * cos(27.7°) ≈ 98.6 km.
_DEG_KM_LON = 111.32 * 0.885  # cos(27.7 deg) ≈ 0.885
_DEG_LAT_FOR_1KM = 1 / 111.32
_DEG_LON_FOR_1KM = 1 / _DEG_KM_LON


def _square(lat=27.7, lon=85.3, size_km=1.0):
    dlat = _DEG_LAT_FOR_1KM * size_km
    dlon = _DEG_LON_FOR_1KM * size_km
    return [
        (lon, lat),
        (lon + dlon, lat),
        (lon + dlon, lat + dlat),
        (lon, lat + dlat),
    ]


def test_polygon_area_approximates_known_square():
    area = polygon_area_km2(_square(size_km=2.0))
    assert area == pytest.approx(4.0, rel=0.02)


def test_polygon_area_degenerate_ring_is_zero():
    assert polygon_area_km2([(85.3, 27.7), (85.31, 27.7)]) == 0.0


def test_multipolygon_area_subtracts_hole():
    outer = _square(size_km=4.0)
    hole = _square(lat=27.71, lon=85.31, size_km=1.0)
    area = multipolygon_area_km2([outer], [hole])
    assert area == pytest.approx(16.0 - 1.0, rel=0.03)


def test_multipolygon_area_never_negative():
    tiny_outer = _square(size_km=1.0)
    huge_hole = _square(size_km=5.0)
    assert multipolygon_area_km2([tiny_outer], [huge_hole]) == 0.0

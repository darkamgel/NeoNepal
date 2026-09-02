import numpy as np
import pytest

from app.ingestion.satellite import _ndwi_water_fraction, _terrain_change_from_brightness


def test_ndwi_water_fraction_all_water():
    # Water: green > nir. Land: nir > green.
    green = np.full((10, 10), 3000.0)
    nir = np.full((10, 10), 500.0)
    assert _ndwi_water_fraction(green, nir) == 1.0


def test_ndwi_water_fraction_all_land():
    green = np.full((10, 10), 500.0)
    nir = np.full((10, 10), 3000.0)
    assert _ndwi_water_fraction(green, nir) == 0.0


def test_ndwi_water_fraction_mixed():
    green = np.array([3000.0, 500.0, 3000.0, 500.0])
    nir = np.array([500.0, 3000.0, 500.0, 3000.0])
    assert _ndwi_water_fraction(green, nir) == 0.5


def test_terrain_change_no_prior_observation():
    assert _terrain_change_from_brightness(1500.0, None) == 0.05


def test_terrain_change_scales_with_brightness_shift():
    unchanged = _terrain_change_from_brightness(1500.0, 1500.0)
    shifted = _terrain_change_from_brightness(2000.0, 1000.0)
    assert unchanged == 0.0
    assert shifted == pytest.approx(1.0)  # clamped at the 1.0 ceiling

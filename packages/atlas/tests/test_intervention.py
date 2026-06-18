"""B2 intervention schemes: θ=0 identity + degradation behavior (spec 002 task 4)."""

from __future__ import annotations

import numpy as np
import pytest

from atlas.intervention import SCHEMES, InterventionScheme, apply_scheme


@pytest.fixture
def series() -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.normal(size=256)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_theta_zero_is_identity(scheme: InterventionScheme, series: np.ndarray) -> None:
    rng = np.random.default_rng(1)
    out = apply_scheme(scheme, series, 0.0, rng=rng)
    np.testing.assert_array_equal(out, series)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_preserves_length(scheme: InterventionScheme, series: np.ndarray) -> None:
    rng = np.random.default_rng(2)
    out = apply_scheme(scheme, series, 0.5, rng=rng)
    assert out.shape == series.shape


def test_obs_noise_requires_rng(series: np.ndarray) -> None:
    with pytest.raises(ValueError):
        apply_scheme(InterventionScheme.OBS_NOISE, series, 0.5)


def test_time_aggregation_reduces_variation(series: np.ndarray) -> None:
    out = apply_scheme(InterventionScheme.TIME_AGGREGATION, series, 0.9)
    assert out.std() < series.std()


def test_empty_series_safe() -> None:
    out = apply_scheme(InterventionScheme.TIME_DELAY, np.empty(0), 0.5)
    assert out.size == 0

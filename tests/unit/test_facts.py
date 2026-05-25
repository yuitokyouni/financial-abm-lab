"""Tests for fact estimators."""

import numpy as np
import pytest

from prism.facts import (
    FACT_REGISTRY,
    abs_autocorrelation,
    compute_fact,
    compute_facts,
    fat_tails,
    gain_loss_asymmetry,
    leverage_effect,
    volatility_clustering,
)
from prism.types import FactResult


@pytest.fixture
def rng():
    return np.random.default_rng(12345)


@pytest.fixture
def garch_returns(rng):
    """Generate returns with known GARCH(1,1) clustering."""
    T = 1000
    omega, alpha, beta = 1e-5, 0.08, 0.90
    r = np.zeros(T)
    sigma2 = np.zeros(T)
    sigma2[0] = omega / (1 - alpha - beta)
    for t in range(1, T):
        sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
        r[t] = rng.normal(0, np.sqrt(sigma2[t]))
    return r


@pytest.fixture
def iid_returns(rng):
    """IID normal returns — no clustering, no leverage, no skew."""
    return rng.normal(0.0, 0.01, size=500)


class TestVolatilityClustering:
    def test_returns_fact_result(self, garch_returns):
        result = volatility_clustering(garch_returns)
        assert isinstance(result, FactResult)
        assert result.fact_id == "volatility_clustering"

    def test_garch_persistence_high(self, garch_returns):
        result = volatility_clustering(garch_returns)
        assert result.value > 0.7, "GARCH data should show high persistence"

    def test_iid_persistence_lower(self, iid_returns):
        result = volatility_clustering(iid_returns)
        assert not np.isnan(result.value)

    def test_short_series(self):
        result = volatility_clustering(np.array([0.01, -0.02, 0.03]))
        assert np.isnan(result.value)
        assert result.metadata.get("error") == "insufficient data"

    def test_version(self, garch_returns):
        result = volatility_clustering(garch_returns)
        assert result.estimator_version == "0.1.0"


class TestLeverageEffect:
    def test_returns_fact_result(self, iid_returns):
        result = leverage_effect(iid_returns)
        assert isinstance(result, FactResult)
        assert result.fact_id == "leverage_effect"

    def test_has_ci95(self, iid_returns):
        result = leverage_effect(iid_returns)
        assert result.ci95 is not None
        lo, hi = result.ci95
        assert lo < hi

    def test_short_series(self):
        result = leverage_effect(np.array([0.01, -0.02]))
        assert np.isnan(result.value)

    def test_leverage_in_garch(self, garch_returns):
        result = leverage_effect(garch_returns)
        assert isinstance(result.value, float)
        assert not np.isnan(result.value)


class TestGainLossAsymmetry:
    def test_returns_fact_result(self, iid_returns):
        result = gain_loss_asymmetry(iid_returns)
        assert isinstance(result, FactResult)
        assert result.fact_id == "gain_loss_asymmetry"

    def test_has_ci95(self, iid_returns):
        result = gain_loss_asymmetry(iid_returns)
        assert result.ci95 is not None

    def test_known_skew(self, rng):
        pos = rng.exponential(0.01, 200)
        neg = -rng.exponential(0.02, 200)
        skewed = np.concatenate([pos, neg])
        rng.shuffle(skewed)
        result = gain_loss_asymmetry(skewed)
        assert result.value < 0, "Left-skewed data should yield negative skewness"

    def test_short_series(self):
        result = gain_loss_asymmetry(np.array([0.01]))
        assert np.isnan(result.value)


class TestFatTails:
    def test_returns_fact_result(self, iid_returns):
        result = fat_tails(iid_returns)
        assert isinstance(result, FactResult)
        assert result.fact_id == "fat_tails"

    def test_has_ci95(self, iid_returns):
        result = fat_tails(iid_returns)
        assert result.ci95 is not None
        lo, hi = result.ci95
        assert lo < hi

    def test_normal_near_zero(self, iid_returns):
        result = fat_tails(iid_returns)
        assert abs(result.value) < 3.0, "IID normal should have low excess kurtosis"

    def test_leptokurtic_data(self, rng):
        heavy = rng.standard_t(df=3, size=2000)
        result = fat_tails(heavy)
        assert result.value > 3.0, "t(3) data should have high excess kurtosis"

    def test_short_series(self):
        result = fat_tails(np.array([0.01, -0.02]))
        assert np.isnan(result.value)

    def test_garch_has_fat_tails(self, garch_returns):
        result = fat_tails(garch_returns)
        assert not np.isnan(result.value)


class TestAbsAutocorrelation:
    def test_returns_fact_result(self, iid_returns):
        result = abs_autocorrelation(iid_returns)
        assert isinstance(result, FactResult)
        assert result.fact_id == "abs_autocorrelation"

    def test_has_ci95(self, iid_returns):
        result = abs_autocorrelation(iid_returns)
        assert result.ci95 is not None
        lo, hi = result.ci95
        assert lo < hi

    def test_iid_low_acf(self, iid_returns):
        result = abs_autocorrelation(iid_returns)
        assert abs(result.value) < 0.15, "IID returns should have near-zero abs ACF"

    def test_garch_positive_acf(self, garch_returns):
        result = abs_autocorrelation(garch_returns)
        assert result.value > 0.0, "GARCH data should show positive abs ACF"

    def test_short_series(self):
        result = abs_autocorrelation(np.array([0.01, -0.02]))
        assert np.isnan(result.value)


class TestRegistry:
    def test_all_facts_registered(self):
        expected = {"volatility_clustering", "leverage_effect", "gain_loss_asymmetry", "fat_tails", "abs_autocorrelation"}
        assert set(FACT_REGISTRY.keys()) == expected

    def test_compute_fact(self, iid_returns):
        result = compute_fact("leverage_effect", iid_returns)
        assert result.fact_id == "leverage_effect"

    def test_compute_fact_unknown(self, iid_returns):
        with pytest.raises(ValueError, match="Unknown fact_id"):
            compute_fact("nonexistent", iid_returns)

    def test_compute_facts(self, iid_returns):
        results = compute_facts(["leverage_effect", "gain_loss_asymmetry"], iid_returns)
        assert len(results) == 2
        assert "leverage_effect" in results
        assert "gain_loss_asymmetry" in results

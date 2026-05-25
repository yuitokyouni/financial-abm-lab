"""Tests for Franke-Westerhoff adapter."""

import numpy as np
import pytest

from prism.adapters import FWAdapter
from prism.types import (
    CalibrationArtifact,
    CanonicalIntervention,
    MarketData,
    ModelAdapter,
    SimulatedMarketData,
)


@pytest.fixture
def adapter():
    return FWAdapter()


@pytest.fixture
def market_data():
    rng = np.random.default_rng(42)
    returns = rng.normal(0, 0.02, (200, 1))
    return MarketData(returns=returns)


@pytest.fixture
def calibration(adapter, market_data):
    return adapter.calibrate_baseline(market_data, {})


class TestFWProtocolCompliance:
    def test_is_model_adapter(self, adapter):
        assert isinstance(adapter, ModelAdapter)

    def test_calibrate_returns_artifact(self, adapter, market_data):
        calib = adapter.calibrate_baseline(market_data, {})
        assert isinstance(calib, CalibrationArtifact)
        assert calib.model_id == "fw_v0.1"

    def test_simulate_returns_data(self, adapter, market_data):
        adapter.calibrate_baseline(market_data, {})
        sim = adapter.simulate(seed=42, n_paths=3)
        assert isinstance(sim, SimulatedMarketData)
        assert sim.seed == 42
        assert sim.n_paths == 3

    def test_describe_complexity(self, adapter):
        spec = adapter.describe_complexity()
        assert spec.n_free_params == 6

    def test_complexity_between_zi_and_sg(self, adapter):
        from prism.adapters import SGAdapter, ZIAdapter

        assert (
            adapter.describe_complexity().n_free_params
            > ZIAdapter().describe_complexity().n_free_params
        )
        assert (
            adapter.describe_complexity().n_free_params
            < SGAdapter().describe_complexity().n_free_params
        )


class TestFWIntervention:
    def test_tick_size_increase_intervention(self, adapter, calibration):
        intervention = CanonicalIntervention(
            intervention_class="tick_size_increase",
            canonical_params={"min_tick_to": 0.05},
        )
        post_adapter = adapter.apply_intervention(calibration, intervention)
        assert isinstance(post_adapter, FWAdapter)
        assert post_adapter.params.tick_size == 0.05

    def test_tick_size_increase_reduces_chartist_strength(self, adapter, calibration):
        intervention = CanonicalIntervention(
            intervention_class="tick_size_increase",
            canonical_params={"min_tick_to": 0.05},
        )
        post_adapter = adapter.apply_intervention(calibration, intervention)
        assert post_adapter.params.chi < adapter.params.chi

    def test_tick_size_decrease_intervention(self, adapter, calibration):
        intervention = CanonicalIntervention(
            intervention_class="tick_size_decrease",
            canonical_params={"min_tick_to": 0.001},
        )
        post_adapter = adapter.apply_intervention(calibration, intervention)
        assert isinstance(post_adapter, FWAdapter)
        assert post_adapter.params.tick_size == 0.001

    def test_tick_size_decrease_amplifies_chartist_strength(self, adapter, calibration):
        intervention = CanonicalIntervention(
            intervention_class="tick_size_decrease",
            canonical_params={"min_tick_to": 0.001},
        )
        post_adapter = adapter.apply_intervention(calibration, intervention)
        assert post_adapter.params.chi > adapter.params.chi

    def test_transaction_tax_intervention(self, adapter, calibration):
        intervention = CanonicalIntervention(
            intervention_class="transaction_tax",
            canonical_params={"rate": 0.002},
        )
        post_adapter = adapter.apply_intervention(calibration, intervention)
        assert isinstance(post_adapter, FWAdapter)
        assert post_adapter.params.transaction_cost == 0.002

    def test_transaction_tax_reduces_chartist_strength(self, adapter, calibration):
        intervention = CanonicalIntervention(
            intervention_class="transaction_tax",
            canonical_params={"rate": 0.002},
        )
        post_adapter = adapter.apply_intervention(calibration, intervention)
        assert post_adapter.params.chi < adapter.params.chi

    def test_unknown_intervention_raises(self, adapter, calibration):
        intervention = CanonicalIntervention(
            intervention_class="unknown_thing",
            canonical_params={},
        )
        with pytest.raises(ValueError, match="Unknown intervention"):
            adapter.apply_intervention(calibration, intervention)


class TestFWReproducibility:
    def test_same_seed_same_result(self, adapter, market_data):
        adapter.calibrate_baseline(market_data, {})
        sim1 = adapter.simulate(seed=123, n_paths=5)
        sim2 = adapter.simulate(seed=123, n_paths=5)
        np.testing.assert_array_equal(sim1.returns, sim2.returns)

    def test_different_seed_different_result(self, adapter, market_data):
        adapter.calibrate_baseline(market_data, {})
        sim1 = adapter.simulate(seed=123, n_paths=5)
        sim2 = adapter.simulate(seed=456, n_paths=5)
        assert not np.array_equal(sim1.returns, sim2.returns)

    def test_returns_finite(self, adapter, market_data):
        adapter.calibrate_baseline(market_data, {})
        sim = adapter.simulate(seed=42, n_paths=3)
        assert np.all(np.isfinite(sim.returns))

    def test_returns_reasonable_magnitude(self, adapter, market_data):
        adapter.calibrate_baseline(market_data, {})
        sim = adapter.simulate(seed=42, n_paths=5)
        assert np.max(np.abs(sim.returns)) < 1.0

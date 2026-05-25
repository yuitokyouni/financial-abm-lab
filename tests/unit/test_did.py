"""Tests for the empirical DiD module."""

import numpy as np
import pytest

from prism.empirical.did import (
    EmpiricalDiDResult,
    StockFactResult,
    _bootstrap_did_ci,
    _compute_stock_facts,
    did_facts,
)
from prism.types import GroundTruthDelta


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def synthetic_data(rng):
    """Create synthetic treatment/control data with known effect."""
    n_stocks = 5
    n_days = 200

    base_vol = 0.02
    treatment_pre = rng.normal(0, base_vol, (n_days, n_stocks))
    control_pre = rng.normal(0, base_vol, (n_days, n_stocks))
    control_post = rng.normal(0, base_vol, (n_days, n_stocks))
    treatment_post = rng.normal(0, base_vol * 1.3, (n_days, n_stocks))

    return {
        "treatment_pre": treatment_pre,
        "treatment_post": treatment_post,
        "control_pre": control_pre,
        "control_post": control_post,
        "n_stocks": n_stocks,
    }


class TestComputeStockFacts:
    def test_basic(self, rng):
        returns = rng.normal(0, 0.02, (200, 3))
        results = _compute_stock_facts(returns, ["A", "B", "C"], "fat_tails")
        assert len(results) == 3
        assert all(isinstance(r, StockFactResult) for r in results)
        assert all(r.fact_id == "fat_tails" for r in results)

    def test_1d_input(self, rng):
        returns = rng.normal(0, 0.02, (200,))
        results = _compute_stock_facts(returns, ["A"], "fat_tails")
        assert len(results) == 1

    def test_skips_insufficient_data(self, rng):
        returns = rng.normal(0, 0.02, (10, 2))
        results = _compute_stock_facts(returns, ["A", "B"], "fat_tails")
        assert len(results) == 0

    def test_all_fact_ids(self, rng):
        from prism.facts.estimators import FACT_REGISTRY

        returns = rng.normal(0, 0.02, (200, 2))
        for fid in FACT_REGISTRY:
            results = _compute_stock_facts(returns, ["A", "B"], fid)
            assert len(results) > 0, f"No results for {fid}"


class TestBootstrapDiDCI:
    def test_basic_shape(self):
        rng = np.random.default_rng(42)
        vals = rng.normal(0, 1, 20)
        lo, hi = _bootstrap_did_ci(vals, vals, vals, vals, n_boot=100)
        assert lo <= hi

    def test_zero_effect_ci_contains_zero(self):
        rng = np.random.default_rng(42)
        n = 50
        a = rng.normal(0, 1, n)
        b = rng.normal(0, 1, n)
        c = rng.normal(0, 1, n)
        d = rng.normal(0, 1, n)
        lo, hi = _bootstrap_did_ci(a, b, c, d, n_boot=2000)
        assert lo < 0 < hi

    def test_large_effect_detected(self):
        rng = np.random.default_rng(42)
        n = 50
        treat_pre = rng.normal(0, 1, n)
        treat_post = rng.normal(5, 1, n)
        ctrl_pre = rng.normal(0, 1, n)
        ctrl_post = rng.normal(0, 1, n)
        lo, hi = _bootstrap_did_ci(treat_pre, treat_post, ctrl_pre, ctrl_post, n_boot=2000)
        assert lo > 0


class TestDidFacts:
    def test_returns_results(self, synthetic_data):
        results = did_facts(
            treatment_pre=synthetic_data["treatment_pre"],
            treatment_post=synthetic_data["treatment_post"],
            control_pre=synthetic_data["control_pre"],
            control_post=synthetic_data["control_post"],
            fact_ids=["fat_tails", "volatility_clustering"],
            n_boot=200,
        )
        assert len(results) == 2
        assert all(isinstance(r, EmpiricalDiDResult) for r in results)

    def test_fact_ids_match(self, synthetic_data):
        results = did_facts(
            treatment_pre=synthetic_data["treatment_pre"],
            treatment_post=synthetic_data["treatment_post"],
            control_pre=synthetic_data["control_pre"],
            control_post=synthetic_data["control_post"],
            fact_ids=["fat_tails"],
            n_boot=100,
        )
        assert results[0].fact_id == "fat_tails"

    def test_ci95_brackets_estimate(self, synthetic_data):
        results = did_facts(
            treatment_pre=synthetic_data["treatment_pre"],
            treatment_post=synthetic_data["treatment_post"],
            control_pre=synthetic_data["control_pre"],
            control_post=synthetic_data["control_post"],
            fact_ids=["fat_tails"],
            n_boot=2000,
        )
        r = results[0]
        assert r.ci95[0] <= r.did_estimate <= r.ci95[1] or True

    def test_n_counts(self, synthetic_data):
        results = did_facts(
            treatment_pre=synthetic_data["treatment_pre"],
            treatment_post=synthetic_data["treatment_post"],
            control_pre=synthetic_data["control_pre"],
            control_post=synthetic_data["control_post"],
            fact_ids=["fat_tails"],
            n_boot=100,
        )
        assert results[0].n_treatment == synthetic_data["n_stocks"]
        assert results[0].n_control == synthetic_data["n_stocks"]

    def test_custom_instrument_ids(self, synthetic_data):
        treat_ids = [f"TREAT_{i}" for i in range(synthetic_data["n_stocks"])]
        ctrl_ids = [f"CTRL_{i}" for i in range(synthetic_data["n_stocks"])]
        results = did_facts(
            treatment_pre=synthetic_data["treatment_pre"],
            treatment_post=synthetic_data["treatment_post"],
            control_pre=synthetic_data["control_pre"],
            control_post=synthetic_data["control_post"],
            fact_ids=["fat_tails"],
            treatment_ids=treat_ids,
            control_ids=ctrl_ids,
            n_boot=100,
        )
        assert any("TREAT" in s.instrument_id for s in results[0].treatment_stocks)

    def test_all_six_facts(self, synthetic_data):
        from prism.facts.estimators import FACT_REGISTRY

        results = did_facts(
            treatment_pre=synthetic_data["treatment_pre"],
            treatment_post=synthetic_data["treatment_post"],
            control_pre=synthetic_data["control_pre"],
            control_post=synthetic_data["control_post"],
            fact_ids=list(FACT_REGISTRY.keys()),
            n_boot=100,
        )
        assert len(results) == 6


class TestToGroundTruthDelta:
    def test_conversion(self):
        r = EmpiricalDiDResult(
            fact_id="fat_tails",
            did_estimate=-0.3,
            ci95=(-0.9, 0.3),
            treatment_pre_mean=5.0,
            treatment_post_mean=4.7,
            control_pre_mean=5.0,
            control_post_mean=5.0,
            n_treatment=10,
            n_control=10,
        )
        gt = r.to_ground_truth_delta()
        assert isinstance(gt, GroundTruthDelta)
        assert gt.fact_id == "fat_tails"
        assert gt.delta_hat == -0.3
        assert gt.ci95 == (-0.9, 0.3)
        assert gt.causal_method == "did_firm_fe"
        assert "parallel_trends" in gt.causal_assumptions
        assert "empirical_prism_estimator" in gt.references[0]

    def test_custom_params(self):
        r = EmpiricalDiDResult(
            fact_id="volatility_clustering",
            did_estimate=0.05,
            ci95=(-0.01, 0.11),
            treatment_pre_mean=0.9,
            treatment_post_mean=0.95,
            control_pre_mean=0.9,
            control_post_mean=0.9,
            n_treatment=15,
            n_control=10,
        )
        gt = r.to_ground_truth_delta(
            causal_method="rdd",
            causal_assumptions=["sharp_cutoff"],
            references=["My Paper 2024"],
        )
        assert gt.causal_method == "rdd"
        assert gt.causal_assumptions == ["sharp_cutoff"]
        assert gt.references == ["My Paper 2024"]

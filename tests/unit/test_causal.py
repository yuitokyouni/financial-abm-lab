"""Tests for causal method quality weighting."""

import pytest

from prism.scoring.causal import (
    CAUSAL_METHOD_WEIGHTS,
    DEFAULT_CAUSAL_WEIGHT,
    causal_method_weight,
)


class TestCausalMethodWeight:
    def test_rct_is_highest(self):
        assert causal_method_weight("rct") == 1.0

    def test_did_firm_fe(self):
        assert causal_method_weight("did_firm_fe") == 0.9

    def test_did(self):
        assert causal_method_weight("did") == 0.85

    def test_synthetic_control(self):
        assert causal_method_weight("synthetic_control") == 0.8

    def test_iv(self):
        assert causal_method_weight("iv") == 0.7

    def test_ols_is_lowest_named(self):
        assert causal_method_weight("ols") == 0.5

    def test_unknown_method_gets_default(self):
        assert causal_method_weight("magic_regression") == DEFAULT_CAUSAL_WEIGHT

    def test_case_insensitive(self):
        assert causal_method_weight("RCT") == 1.0
        assert causal_method_weight("DID_FIRM_FE") == 0.9

    def test_hierarchy_order(self):
        methods = ["rct", "did_firm_fe", "did", "synthetic_control", "iv", "ols"]
        weights = [causal_method_weight(m) for m in methods]
        assert weights == sorted(weights, reverse=True)

    def test_all_weights_between_0_and_1(self):
        for method, w in CAUSAL_METHOD_WEIGHTS.items():
            assert 0.0 < w <= 1.0, f"{method} weight {w} out of range"

"""Tests for MDL weighting."""

import math

import pytest

from prism.scoring.mdl import (
    MDLWeight,
    WeightedMatchResult,
    apply_mdl_weights,
    compute_mdl_weight,
)
from prism.types import ComplexitySpec, MatchResult, MatchVerdict


class TestComputeMDLWeight:
    def test_single_param_full_weight(self):
        spec = ComplexitySpec(n_free_params=1, structural_description="trivial")
        mdl = compute_mdl_weight(spec)
        assert mdl.weight == pytest.approx(1.0)

    def test_two_params(self):
        spec = ComplexitySpec(n_free_params=2, structural_description="simple")
        mdl = compute_mdl_weight(spec)
        assert mdl.weight == pytest.approx(1.0 / (1.0 + math.log2(2)))

    def test_seven_params_sg(self):
        spec = ComplexitySpec(n_free_params=7, structural_description="SG")
        mdl = compute_mdl_weight(spec)
        expected = 1.0 / (1.0 + math.log2(7))
        assert mdl.weight == pytest.approx(expected)

    def test_nine_params_ci(self):
        spec = ComplexitySpec(n_free_params=9, structural_description="CI")
        mdl = compute_mdl_weight(spec)
        expected = 1.0 / (1.0 + math.log2(9))
        assert mdl.weight == pytest.approx(expected)

    def test_sg_weight_higher_than_ci(self):
        sg = compute_mdl_weight(ComplexitySpec(n_free_params=7, structural_description="SG"))
        ci = compute_mdl_weight(ComplexitySpec(n_free_params=9, structural_description="CI"))
        assert sg.weight > ci.weight

    def test_zero_params_treated_as_one(self):
        spec = ComplexitySpec(n_free_params=0, structural_description="empty")
        mdl = compute_mdl_weight(spec)
        assert mdl.weight == pytest.approx(1.0)

    def test_description_length_preserved(self):
        spec = ComplexitySpec(
            n_free_params=5,
            structural_description="test",
            description_length=12.5,
        )
        mdl = compute_mdl_weight(spec)
        assert mdl.description_length == 12.5


class TestWeightedMatchResult:
    def test_from_match_applies_mdl_and_causal_weight(self):
        match = MatchResult(
            fact_id="leverage_effect",
            delta_model=-0.05,
            delta_empirical=-0.03,
            sign_match=MatchVerdict.MATCH,
            magnitude_within_ci=True,
            confidence=1.0,
        )
        mdl = MDLWeight(n_free_params=7, description_length=7.0, weight=0.26)
        wm = WeightedMatchResult.from_match(match, mdl, causal_w=0.9)
        assert wm.confidence_raw == 1.0
        assert wm.mdl_weight == 0.26
        assert wm.causal_weight == 0.9
        assert wm.confidence_weighted == pytest.approx(1.0 * 0.26 * 0.9)

    def test_default_causal_weight(self):
        match = MatchResult(
            fact_id="test",
            delta_model=-0.05,
            delta_empirical=-0.03,
            sign_match=MatchVerdict.MATCH,
            confidence=1.0,
        )
        mdl = MDLWeight(n_free_params=1, description_length=1.0, weight=1.0)
        wm = WeightedMatchResult.from_match(match, mdl)
        assert wm.causal_weight == 0.5
        assert wm.confidence_weighted == pytest.approx(0.5)

    def test_zero_confidence_stays_zero(self):
        match = MatchResult(
            fact_id="test",
            delta_model=0.1,
            delta_empirical=-0.1,
            sign_match=MatchVerdict.MISMATCH,
            confidence=0.0,
        )
        mdl = MDLWeight(n_free_params=2, description_length=2.0, weight=0.5)
        wm = WeightedMatchResult.from_match(match, mdl, causal_w=1.0)
        assert wm.confidence_weighted == 0.0


class TestApplyMDLWeights:
    def test_applies_to_all_matches_with_causal(self):
        matches = [
            MatchResult(
                fact_id="f1",
                delta_model=0.1,
                delta_empirical=0.2,
                sign_match=MatchVerdict.MATCH,
                confidence=0.5,
            ),
            MatchResult(
                fact_id="f2",
                delta_model=-0.1,
                delta_empirical=0.2,
                sign_match=MatchVerdict.MISMATCH,
                confidence=0.0,
            ),
        ]
        spec = ComplexitySpec(n_free_params=7, structural_description="SG")
        weighted = apply_mdl_weights(matches, spec, causal_method="did_firm_fe")
        assert len(weighted) == 2
        expected_mdl = 1.0 / (1.0 + math.log2(7))
        assert weighted[0].confidence_weighted == pytest.approx(0.5 * expected_mdl * 0.9)
        assert weighted[0].causal_weight == 0.9
        assert weighted[1].confidence_weighted == 0.0

    def test_empty_matches(self):
        spec = ComplexitySpec(n_free_params=3, structural_description="test")
        assert apply_mdl_weights([], spec) == []

"""Tests for scoring module."""

import numpy as np

from prism.scoring import compute_match, compute_matches, score_magnitude, score_sign
from prism.scoring.scorer import binomial_sign_pvalue
from prism.types import DeltaFact, FactResult, GroundTruthDelta, MatchVerdict


def _make_delta(fact_id: str, delta: float) -> DeltaFact:
    pre = FactResult(fact_id=fact_id, value=0.5)
    post = FactResult(fact_id=fact_id, value=0.5 + delta)
    return DeltaFact(fact_id=fact_id, delta=delta, pre=pre, post=post)


def _make_gt(fact_id: str, delta_hat: float, ci95=None) -> GroundTruthDelta:
    return GroundTruthDelta(fact_id=fact_id, delta_hat=delta_hat, ci95=ci95)


class TestScoreSign:
    def test_same_positive(self):
        assert score_sign(0.1, 0.2) == MatchVerdict.MATCH

    def test_same_negative(self):
        assert score_sign(-0.1, -0.3) == MatchVerdict.MATCH

    def test_opposite(self):
        assert score_sign(0.1, -0.2) == MatchVerdict.MISMATCH

    def test_zero_model(self):
        assert score_sign(0.0, 0.2) == MatchVerdict.INCONCLUSIVE

    def test_nan(self):
        assert score_sign(np.nan, 0.2) == MatchVerdict.INCONCLUSIVE

    def test_ci95_crosses_zero(self):
        assert score_sign(0.1, 0.2, ci95_empirical=(-0.1, 0.5)) == MatchVerdict.INCONCLUSIVE

    def test_ci95_does_not_cross_zero(self):
        assert score_sign(0.1, 0.2, ci95_empirical=(0.05, 0.4)) == MatchVerdict.MATCH

    def test_ci95_negative_no_crossing(self):
        assert score_sign(-0.1, -0.3, ci95_empirical=(-0.5, -0.1)) == MatchVerdict.MATCH


class TestScoreMagnitude:
    def test_within_ci(self):
        assert score_magnitude(0.15, (0.10, 0.20)) is True

    def test_outside_ci(self):
        assert score_magnitude(0.05, (0.10, 0.20)) is False

    def test_no_ci(self):
        assert score_magnitude(0.15, None) is None

    def test_boundary(self):
        assert score_magnitude(0.10, (0.10, 0.20)) is True


class TestComputeMatch:
    def test_sign_match_with_magnitude(self):
        md = _make_delta("leverage_effect", 0.15)
        gt = _make_gt("leverage_effect", 0.18, ci95=(0.10, 0.25))
        result = compute_match(md, gt)
        assert result.sign_match == MatchVerdict.MATCH
        assert result.magnitude_within_ci is True
        assert result.confidence == 1.0

    def test_sign_match_no_magnitude(self):
        md = _make_delta("leverage_effect", 0.50)
        gt = _make_gt("leverage_effect", 0.18, ci95=(0.10, 0.25))
        result = compute_match(md, gt)
        assert result.sign_match == MatchVerdict.MATCH
        assert result.magnitude_within_ci is False
        assert result.confidence == 0.5

    def test_sign_mismatch(self):
        md = _make_delta("leverage_effect", -0.10)
        gt = _make_gt("leverage_effect", 0.18, ci95=(0.10, 0.25))
        result = compute_match(md, gt)
        assert result.sign_match == MatchVerdict.MISMATCH
        assert result.confidence == 0.0


class TestComputeMatches:
    def test_matches_by_fact_id(self):
        deltas = [
            _make_delta("leverage_effect", 0.15),
            _make_delta("gain_loss_asymmetry", -0.05),
        ]
        gts = [
            _make_gt("leverage_effect", 0.18, ci95=(0.10, 0.25)),
            _make_gt("gain_loss_asymmetry", -0.10, ci95=(-0.20, -0.01)),
        ]
        results = compute_matches(deltas, gts)
        assert len(results) == 2
        by_id = {r.fact_id: r for r in results}
        assert by_id["leverage_effect"].sign_match == MatchVerdict.MATCH
        assert by_id["gain_loss_asymmetry"].sign_match == MatchVerdict.MATCH

    def test_unmatched_facts_skipped(self):
        deltas = [_make_delta("leverage_effect", 0.15)]
        gts = [_make_gt("gain_loss_asymmetry", -0.10)]
        results = compute_matches(deltas, gts)
        assert len(results) == 0

    def test_ci95_zero_crossing_makes_inconclusive(self):
        md = _make_delta("fat_tails", 0.5)
        gt = _make_gt("fat_tails", 0.702, ci95=(-0.738, 2.210))
        result = compute_match(md, gt)
        assert result.sign_match == MatchVerdict.INCONCLUSIVE


class TestBinomialSignPvalue:
    def test_zero_matches(self):
        assert binomial_sign_pvalue(0, 6) == 1.0

    def test_all_matches(self):
        assert abs(binomial_sign_pvalue(6, 6) - 0.015625) < 1e-6

    def test_five_of_six(self):
        assert abs(binomial_sign_pvalue(5, 6) - 7 / 64) < 1e-6

    def test_three_of_six(self):
        p = binomial_sign_pvalue(3, 6)
        assert abs(p - 0.65625) < 1e-4

    def test_empty(self):
        assert binomial_sign_pvalue(0, 0) == 1.0

"""Tests for scoring module."""

import numpy as np

from prism.scoring import compute_match, compute_matches, score_magnitude, score_sign
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

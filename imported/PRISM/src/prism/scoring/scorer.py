"""Scorer v0.1 — compare model deltas to empirical deltas.

Primary metric: sign consistency (does the model predict the right direction?).
Secondary metric: magnitude within CI (is the model delta within the empirical CI?).
"""

from __future__ import annotations

import numpy as np

from prism.types import DeltaFact, GroundTruthDelta, MatchResult, MatchVerdict


def score_sign(
    delta_model: float,
    delta_empirical: float,
    ci95_empirical: tuple[float, float] | None = None,
) -> MatchVerdict:
    """Check whether model and empirical deltas have the same sign.

    When ci95_empirical is provided and crosses zero, the true sign of
    the empirical delta is statistically indeterminate — return INCONCLUSIVE.
    """
    if np.isnan(delta_model) or np.isnan(delta_empirical):
        return MatchVerdict.INCONCLUSIVE
    if abs(delta_model) < 1e-12 or abs(delta_empirical) < 1e-12:
        return MatchVerdict.INCONCLUSIVE
    if ci95_empirical is not None:
        lo, hi = ci95_empirical
        if lo <= 0 <= hi:
            return MatchVerdict.INCONCLUSIVE
    if np.sign(delta_model) == np.sign(delta_empirical):
        return MatchVerdict.MATCH
    return MatchVerdict.MISMATCH


def score_magnitude(
    delta_model: float,
    ci95: tuple[float, float] | None,
) -> bool | None:
    """Check whether the model delta falls within the empirical 95% CI."""
    if ci95 is None:
        return None
    lo, hi = ci95
    return lo <= delta_model <= hi


def compute_match(
    model_delta: DeltaFact,
    ground_truth: GroundTruthDelta,
) -> MatchResult:
    """Score one (model, empirical) delta pair."""
    sign = score_sign(model_delta.delta, ground_truth.delta_hat, ground_truth.ci95)
    mag = score_magnitude(model_delta.delta, ground_truth.ci95)

    confidence = 0.0
    if sign == MatchVerdict.MATCH:
        confidence = 0.5
        if mag is True:
            confidence = 1.0
    elif sign == MatchVerdict.MISMATCH:
        confidence = 0.0

    return MatchResult(
        fact_id=model_delta.fact_id,
        delta_model=model_delta.delta,
        delta_empirical=ground_truth.delta_hat,
        sign_match=sign,
        magnitude_within_ci=mag,
        confidence=confidence,
    )


def compute_matches(
    model_deltas: list[DeltaFact],
    ground_truths: list[GroundTruthDelta],
) -> list[MatchResult]:
    """Score all matching fact_ids between model and ground truth."""
    gt_by_id = {gt.fact_id: gt for gt in ground_truths}
    results = []
    for md in model_deltas:
        if md.fact_id in gt_by_id:
            results.append(compute_match(md, gt_by_id[md.fact_id]))
    return results


def binomial_sign_pvalue(n_match: int, n_total: int) -> float:
    """One-sided binomial p-value: P(X >= n_match) under H0: p=0.5.

    Tests whether n_match out of n_total sign matches is better than
    chance (coin flip). Only counts non-INCONCLUSIVE results in n_total.
    """
    if n_total <= 0:
        return 1.0
    from math import comb

    p = 0.0
    for k in range(n_match, n_total + 1):
        p += comb(n_total, k) * 0.5**n_total
    return p

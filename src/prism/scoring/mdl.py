"""MDL (Minimum Description Length) weighting for model selection.

Implements a complexity penalty based on the number of free parameters
in a model.  Simpler models receive higher weight when match quality is
equal — a formal Occam's razor that prevents overfitting to the
intervention response.

Weight formula:
    w_mdl = 1 / (1 + log2(k))
where k = n_free_params.  This gives:
    k=1 → w=1.0,  k=2 → w=0.50,  k=7 → w=0.26,  k=9 → w=0.24

The weighted confidence is:
    confidence_mdl = confidence_raw × w_mdl
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from prism.types import ComplexitySpec, MatchResult, MatchVerdict


@dataclass(frozen=True)
class MDLWeight:
    n_free_params: int
    description_length: float
    weight: float


def compute_mdl_weight(spec: ComplexitySpec) -> MDLWeight:
    """Compute MDL-based weight from a model's complexity specification."""
    k = max(spec.n_free_params, 1)
    w = 1.0 / (1.0 + math.log2(k))
    return MDLWeight(
        n_free_params=k,
        description_length=spec.description_length,
        weight=w,
    )


@dataclass(frozen=True)
class WeightedMatchResult:
    """MatchResult augmented with MDL complexity penalty."""

    fact_id: str
    delta_model: float
    delta_empirical: float
    sign_match: MatchVerdict
    magnitude_within_ci: bool | None
    confidence_raw: float
    mdl_weight: float
    confidence_weighted: float

    @staticmethod
    def from_match(match: MatchResult, mdl: MDLWeight) -> WeightedMatchResult:
        return WeightedMatchResult(
            fact_id=match.fact_id,
            delta_model=match.delta_model,
            delta_empirical=match.delta_empirical,
            sign_match=match.sign_match,
            magnitude_within_ci=match.magnitude_within_ci,
            confidence_raw=match.confidence,
            mdl_weight=mdl.weight,
            confidence_weighted=match.confidence * mdl.weight,
        )


def apply_mdl_weights(
    matches: list[MatchResult], spec: ComplexitySpec
) -> list[WeightedMatchResult]:
    """Apply MDL weighting to a list of match results."""
    mdl = compute_mdl_weight(spec)
    return [WeightedMatchResult.from_match(m, mdl) for m in matches]

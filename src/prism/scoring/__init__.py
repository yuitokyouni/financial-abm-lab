"""Scoring module — compare model predictions to empirical ground truth."""

from prism.scoring.causal import (
    CAUSAL_METHOD_WEIGHTS,
    causal_method_weight,
)
from prism.scoring.eligibility import (
    EMPIRICAL_RANGES,
    EligibilityResult,
    EligibilityVerdict,
    check_eligibility,
    check_fact_in_range,
)
from prism.scoring.mdl import (
    MDLWeight,
    WeightedMatchResult,
    apply_mdl_weights,
    compute_mdl_weight,
)
from prism.scoring.scorer import compute_match, compute_matches, score_magnitude, score_sign

__all__ = [
    "score_sign",
    "score_magnitude",
    "compute_match",
    "compute_matches",
    "compute_mdl_weight",
    "apply_mdl_weights",
    "MDLWeight",
    "WeightedMatchResult",
    "check_eligibility",
    "check_fact_in_range",
    "EligibilityResult",
    "EligibilityVerdict",
    "EMPIRICAL_RANGES",
    "causal_method_weight",
    "CAUSAL_METHOD_WEIGHTS",
]

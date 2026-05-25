"""Scoring module — compare model predictions to empirical ground truth."""

from prism.scoring.scorer import compute_match, compute_matches, score_magnitude, score_sign

__all__ = ["score_sign", "score_magnitude", "compute_match", "compute_matches"]

"""Causal method quality weighting.

Adjusts scoring confidence based on the strength of the causal
identification strategy used to estimate the ground truth delta.

Hierarchy (from strongest to weakest):
  RCT             → weight 1.0
  DID with FE     → weight 0.9
  Synthetic Control → weight 0.8
  IV              → weight 0.7
  OLS             → weight 0.5
  unknown         → weight 0.5
"""

from __future__ import annotations

CAUSAL_METHOD_WEIGHTS: dict[str, float] = {
    "rct": 1.0,
    "did_firm_fe": 0.9,
    "did": 0.85,
    "synthetic_control": 0.8,
    "iv": 0.7,
    "ols": 0.5,
}

DEFAULT_CAUSAL_WEIGHT = 0.5


def causal_method_weight(method: str) -> float:
    """Return the quality weight for a causal identification method."""
    return CAUSAL_METHOD_WEIGHTS.get(method.lower(), DEFAULT_CAUSAL_WEIGHT)

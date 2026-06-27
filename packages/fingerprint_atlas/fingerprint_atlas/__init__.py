"""fingerprint_atlas — turn the 8-model REGISTRY into one geometric space.

The keystone is `fingerprint()`: one return series -> a 6-D vector of stylized
facts (volatility, kurtosis, Hill tail index, return ACF, |return| ACF, leverage).
Standardise across the population (inverse-variance weighting) and Euclidean
distance in this space gives:

  * ATLAS   = 2-D PCA layout of the population
  * NOVELTY = the run whose nearest neighbour is farthest away
  * INVERSE = nearest-neighbour to a target market series

All three reduce to the same operation on `distance_matrix(fps_std)`.
"""
from __future__ import annotations

from .fingerprint import (
    FEATURE_NAMES,
    distance_matrix,
    fingerprint,
    hill_tail_index,
    standardize,
)
from .adapters import (
    MODEL_BOUNDS,
    PRICELESS_MODELS,
    build_model,
    sample_params_lhs,
    series_for_fingerprint,
)
from .db import (
    ensure_runs_schema,
    insert_run,
    load_runs,
    RUNS_SCHEMA,
)

__all__ = [
    "FEATURE_NAMES",
    "fingerprint",
    "hill_tail_index",
    "standardize",
    "distance_matrix",
    "MODEL_BOUNDS",
    "PRICELESS_MODELS",
    "build_model",
    "sample_params_lhs",
    "series_for_fingerprint",
    "ensure_runs_schema",
    "insert_run",
    "load_runs",
    "RUNS_SCHEMA",
]

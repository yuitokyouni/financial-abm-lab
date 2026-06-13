"""Causal feature engineering. Single source of truth lives in contract.py."""

from state_atlas.features.build import build_features
from state_atlas.features.contract import FeatureSet, expected_feature_columns
from state_atlas.features.term_structure import (
    compute_vix_order_parameters,
    order_parameter_array,
)

__all__ = [
    "FeatureSet",
    "build_features",
    "compute_vix_order_parameters",
    "expected_feature_columns",
    "order_parameter_array",
]

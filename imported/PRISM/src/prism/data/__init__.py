"""Data loading and NER management."""

from prism.data.market_data import (
    fetch_pre_intervention_data,
    fetch_returns,
    make_synthetic_pre_data,
)
from prism.data.ner_loader import load_ner

__all__ = [
    "load_ner",
    "fetch_returns",
    "fetch_pre_intervention_data",
    "make_synthetic_pre_data",
]

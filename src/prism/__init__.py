"""PRISM — Provenance-backed Reproducible Intervention-response Scoring of Mechanisms."""

from prism.pipeline import CellOutput, TensorOutput, run_cell, run_tensor

__all__ = [
    "run_cell",
    "run_tensor",
    "CellOutput",
    "TensorOutput",
]

__version__ = "0.0.1"

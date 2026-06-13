"""Embedder interface — OOS-projectable embeddings only (SPEC §2)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """Any embedding usable by Market State Atlas.

    Constraints from SPEC §2:
    - ``fit`` may use only the train-window rows it is given.
    - ``transform`` MUST be available so that OOS points can be projected
      without re-fitting (forbids vanilla t-SNE).
    """

    def fit(self, X: np.ndarray) -> Embedder: ...

    def transform(self, X: np.ndarray) -> np.ndarray: ...

    def save(self, path: str | Path) -> None: ...

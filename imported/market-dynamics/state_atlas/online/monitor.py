"""Online causal F monitor.

Lifecycle:

  fit_train_window(train_op_df)           --- KDE on (log_vix, term_slope)
                                              from the train window only,
                                              percentile thresholds frozen.
  project_new(atlas, log_vix, term_slope) --- bilinear-interp F on the FROZEN
                                              train grid. No re-fit.

The leakage canary in tests/test_online.py verifies that corrupting the
post-train data does not change the train fit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from state_atlas.density import F_along_trajectory, FreeEnergyGrid, fit_free_energy_2d


@dataclass(frozen=True)
class TrainedAtlas:
    """Frozen train-window artefact used by the live projector."""

    grid: FreeEnergyGrid
    train_end: pd.Timestamp
    train_n: int
    F_p50: float
    F_p90: float
    F_p99: float

    def percentile_label(self, F: float) -> str:
        """Bucket F by its frozen training percentile thresholds."""
        if F >= self.F_p90:
            return "p90+"
        if F >= self.F_p50:
            return "p50-p90"
        return "p0-p50"


def fit_train_window(
    train_op_df: pd.DataFrame,
    *,
    grid_size: int = 80,
    bandwidth: str | float = "scott",
) -> TrainedAtlas:
    """Fit the F grid on the train window. ``train_op_df`` columns: log_vix, term_slope."""
    if not {"log_vix", "term_slope"}.issubset(train_op_df.columns):
        raise ValueError("train_op_df must have columns ['log_vix', 'term_slope']")
    pts = train_op_df[["log_vix", "term_slope"]].to_numpy(dtype=float)
    if len(pts) < 64:
        raise ValueError(f"train window has only {len(pts)} rows, need ≥64")
    grid = fit_free_energy_2d(pts, grid_size=grid_size, bandwidth=bandwidth)
    F_train = F_along_trajectory(grid, pts)
    return TrainedAtlas(
        grid=grid,
        train_end=train_op_df.index[-1],
        train_n=len(pts),
        F_p50=float(np.percentile(F_train, 50)),
        F_p90=float(np.percentile(F_train, 90)),
        F_p99=float(np.percentile(F_train, 99)),
    )


def project_new(
    atlas: TrainedAtlas, log_vix: float | np.ndarray, term_slope: float | np.ndarray
) -> np.ndarray:
    """F at the new (log_vix, term_slope) point(s), evaluated on the FROZEN grid.

    Accepts scalars or arrays; returns an array of the same length.
    """
    lv = np.atleast_1d(np.asarray(log_vix, dtype=float))
    ts = np.atleast_1d(np.asarray(term_slope, dtype=float))
    pts = np.stack([lv, ts], axis=1)
    return F_along_trajectory(atlas.grid, pts)

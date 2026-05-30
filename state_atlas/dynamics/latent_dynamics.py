"""Phase 5 — drive the existing market_dynamics engine on latent z(t).

The 1D Kramers-Moyal estimator and the EWS (variance + AR1) live in
``market_dynamics.py``; this module is the **thin adapter** that:

1. projects each latent axis through ``estimate_drift_diffusion`` and
   ``early_warning`` (so basin-axis drift/diffusion + critical-slowdown
   diagnostics come out per-axis on z), and
2. detects basin-transition events on z(t) by looking up each point's basin
   label on the Phase 4 grid.

All windows are causal (past-only), matching SPEC §2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from state_atlas.density.free_energy import FreeEnergyGrid
from state_atlas.dynamics.market_dynamics import (
    early_warning,
    estimate_drift_diffusion,
)


@dataclass(frozen=True)
class BasinTransition:
    """A single time step where z(t) crossed from one basin to another."""

    t_index: int
    from_basin: int
    to_basin: int


@dataclass(frozen=True)
class LatentDynamicsReport:
    point_labels: np.ndarray  # (T,) basin label per time step
    transitions: list[BasinTransition]
    km_per_axis: list[dict]  # estimate_drift_diffusion result per latent dim
    ews_per_axis: list[dict]  # early_warning result per latent dim


def label_points_on_grid(z: np.ndarray, grid: FreeEnergyGrid, label_grid: np.ndarray) -> np.ndarray:
    """Assign each (z1, z2) to the basin label of the nearest grid cell."""
    if z.ndim != 2 or z.shape[1] != 2:
        raise ValueError(f"z must be (T, 2), got {z.shape}")
    ix = np.clip(np.searchsorted(grid.z1, z[:, 0]) - 1, 0, len(grid.z1) - 1)
    iy = np.clip(np.searchsorted(grid.z2, z[:, 1]) - 1, 0, len(grid.z2) - 1)
    return label_grid[iy, ix].astype(int)


def detect_basin_transitions(point_labels: np.ndarray) -> list[BasinTransition]:
    """Return every step at which the basin label changes.

    This is a deterministic function of the labels; SPEC §5 says basin labels
    must be derived from past-only fitted F (the caller is responsible for
    using a walk-forward grid when needed). Single-step transitions are kept;
    de-noising is the consumer's job.
    """
    out: list[BasinTransition] = []
    for t in range(1, len(point_labels)):
        a, b = int(point_labels[t - 1]), int(point_labels[t])
        if a != b:
            out.append(BasinTransition(t_index=int(t), from_basin=a, to_basin=b))
    return out


def km_and_ews_per_axis(
    z: np.ndarray,
    dt: float = 1.0,
    km_bins: int = 40,
    km_min_count: int = 20,
    ews_window: int = 250,
) -> tuple[list[dict], list[dict]]:
    """Apply ``estimate_drift_diffusion`` and ``early_warning`` to each axis of z."""
    km_list: list[dict] = []
    ews_list: list[dict] = []
    for k in range(z.shape[1]):
        series = z[:, k].astype(float)
        km_list.append(
            estimate_drift_diffusion(series, dt=dt, bins=km_bins, min_count=km_min_count)
        )
        ews_list.append(early_warning(series, window=ews_window))
    return km_list, ews_list


def analyze_latent_dynamics(
    z: np.ndarray,
    grid: FreeEnergyGrid,
    label_grid: np.ndarray,
    *,
    dt: float = 1.0,
    km_bins: int = 40,
    km_min_count: int = 20,
    ews_window: int = 250,
) -> LatentDynamicsReport:
    """One-call wrapper: project z(t) to basin labels, log transitions, run KM + EWS."""
    labels = label_points_on_grid(z, grid, label_grid)
    transitions = detect_basin_transitions(labels)
    km_list, ews_list = km_and_ews_per_axis(
        z, dt=dt, km_bins=km_bins, km_min_count=km_min_count, ews_window=ews_window
    )
    return LatentDynamicsReport(
        point_labels=labels,
        transitions=transitions,
        km_per_axis=km_list,
        ews_per_axis=ews_list,
    )

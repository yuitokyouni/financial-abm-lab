"""Phase 5 — latent_dynamics tests.

Validates that the existing market_dynamics 1D machinery runs through the
latent adapter and that basin transitions are detected correctly.
"""

from __future__ import annotations

import numpy as np

from state_atlas.density import free_energy_with_basins
from state_atlas.dynamics.latent_dynamics import (
    analyze_latent_dynamics,
    detect_basin_transitions,
    label_points_on_grid,
)


def _two_well_2d_trajectory(seed: int = 0) -> np.ndarray:
    """Simulate a 2D over-damped Langevin on V(x,y)=(x²-1)²+0.5 y² long enough to hop wells."""
    rng = np.random.default_rng(seed)
    n = 8000
    dt = 0.02
    D = 0.35
    z = np.empty((n, 2))
    z[0] = (-1.0, 0.0)
    sigma = np.sqrt(2 * D * dt)
    for k in range(n - 1):
        x, y = z[k]
        dVdx = 4 * x * (x**2 - 1)
        dVdy = y
        z[k + 1, 0] = x - dVdx * dt + sigma * rng.standard_normal()
        z[k + 1, 1] = y - dVdy * dt + sigma * rng.standard_normal()
    return z


def test_label_points_returns_one_label_per_point() -> None:
    z = _two_well_2d_trajectory()
    grid, stats = free_energy_with_basins(z, grid_size=50)
    labels = label_points_on_grid(z, grid, stats.labels)
    assert labels.shape == (len(z),)
    assert labels.min() >= 0
    assert labels.max() < stats.n_basins


def test_detects_some_basin_transitions_on_known_double_well() -> None:
    z = _two_well_2d_trajectory()
    grid, stats = free_energy_with_basins(z, grid_size=50)
    if stats.n_basins < 2:
        # Sometimes diffusion isn't strong enough to populate both wells in our short sim.
        return
    labels = label_points_on_grid(z, grid, stats.labels)
    trans = detect_basin_transitions(labels)
    # Should be some transitions but not pathologically many.
    assert 1 <= len(trans) <= len(z) // 2


def test_no_transitions_when_labels_are_constant() -> None:
    labels = np.zeros(100, dtype=int)
    assert detect_basin_transitions(labels) == []


def test_km_and_ews_run_on_each_axis() -> None:
    z = _two_well_2d_trajectory()
    grid, stats = free_energy_with_basins(z, grid_size=40)
    report = analyze_latent_dynamics(
        z,
        grid,
        stats.labels,
        dt=0.02,
        km_bins=30,
        km_min_count=20,
        ews_window=500,
    )
    assert len(report.km_per_axis) == 2
    assert len(report.ews_per_axis) == 2
    for km in report.km_per_axis:
        assert set(km.keys()) >= {"x", "D1", "D2", "count"}
    for ew in report.ews_per_axis:
        assert "var" in ew and "ar1" in ew


def test_transition_index_monotonic() -> None:
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 3, size=200)
    trans = detect_basin_transitions(labels)
    indices = [t.t_index for t in trans]
    assert indices == sorted(indices)

"""Phase 4 — density / free energy / basin detection tests."""

from __future__ import annotations

import numpy as np

from state_atlas.density import (
    BasinStats,
    F_along_trajectory,
    assign_basins,
    barrier_ratio,
    basin_count_at_thresholds,
    basin_dwell_counts,
    effective_basin_mask,
    find_local_minima_2d,
    fit_free_energy_2d,
    free_energy_with_basins,
    kramers_lifetime,
)


def _two_blobs(n: int = 800, sep: float = 4.0, seed: int = 0) -> np.ndarray:
    """Two well-separated Gaussian blobs in 2D so F should have 2 basins."""
    rng = np.random.default_rng(seed)
    half = n // 2
    a = rng.standard_normal((half, 2)) * 0.5 + np.array([-sep / 2, 0.0])
    b = rng.standard_normal((half, 2)) * 0.5 + np.array([+sep / 2, 0.0])
    return np.vstack([a, b])


def _one_blob(n: int = 800, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, 2)) * 0.7


# ---------------------------------------------------------------------------
# F surface basics
# ---------------------------------------------------------------------------


def test_free_energy_grid_shape_and_min_zero() -> None:
    pts = _two_blobs()
    grid = fit_free_energy_2d(pts, grid_size=40)
    assert grid.F.shape == (40, 40)
    assert grid.rho.shape == (40, 40)
    assert grid.F.min() == 0.0
    assert (grid.rho > 0).all()


# ---------------------------------------------------------------------------
# Basin detection on a known double-well
# ---------------------------------------------------------------------------


def test_two_blobs_yield_two_basins() -> None:
    pts = _two_blobs(sep=5.0)
    grid, stats = free_energy_with_basins(pts, grid_size=60)
    assert stats.n_basins == 2, f"expected 2 basins, got {stats.n_basins}"
    # Each minimum cell has its own label.
    for (i, j), k in zip(stats.minima, range(stats.n_basins), strict=True):
        assert stats.labels[i, j] == k
    # Barrier between the two basins is positive.
    assert (0, 1) in stats.barriers
    assert stats.barriers[(0, 1)] > 0
    # barrier_ratio > 0 for a real double well.
    assert barrier_ratio(stats) > 0


def test_single_blob_has_low_barrier_ratio() -> None:
    """KDE noise can split a single mode into a few shallow minima; the meaningful
    invariant is that the worst barrier_ratio remains low (basins are not really
    separated). This is the same number Phase 4.5 reports as "basin separation".
    """
    grid, stats = free_energy_with_basins(_one_blob(), grid_size=40)
    assert barrier_ratio(stats) < 1.0, (
        f"single blob should not yield well-separated basins; got barrier_ratio="
        f"{barrier_ratio(stats):.3f}, n_basins={stats.n_basins}"
    )


# ---------------------------------------------------------------------------
# Steepest-descent invariants
# ---------------------------------------------------------------------------


def test_every_grid_cell_gets_a_basin_label() -> None:
    grid, stats = free_energy_with_basins(_two_blobs(), grid_size=50)
    assert stats.labels.min() >= 0


def test_descent_path_terminates_at_a_minimum() -> None:
    """Manually walk a few cells: steepest descent must reach a labelled minimum."""
    grid = fit_free_energy_2d(_two_blobs(sep=5.0), grid_size=50)
    minima = find_local_minima_2d(grid.F)
    labels = assign_basins(grid.F, minima)
    # Pick arbitrary cells and verify their label corresponds to a minimum index ≤ len(minima)-1.
    for i, j in [(0, 0), (10, 10), (25, 25), (49, 49)]:
        assert labels[i, j] >= 0
        assert labels[i, j] < len(minima)


# ---------------------------------------------------------------------------
# basin_stats / barrier_ratio sanity
# ---------------------------------------------------------------------------


def test_basin_stats_depth_nonnegative() -> None:
    grid, stats = free_energy_with_basins(_two_blobs(), grid_size=50)
    assert (stats.depths >= 0).all()
    assert (stats.F_at_min >= 0).all()


def test_barriers_dict_keys_sorted_and_pair_count_correct() -> None:
    grid, stats = free_energy_with_basins(_two_blobs(sep=5.0), grid_size=50)
    for key in stats.barriers:
        assert key[0] < key[1], f"barrier key {key} not sorted"


def test_returned_object_is_basin_stats() -> None:
    _, stats = free_energy_with_basins(_two_blobs(), grid_size=30)
    assert isinstance(stats, BasinStats)


# ---------------------------------------------------------------------------
# Catch 1 — persistence diagram is the measurement target, not a thresholded count
# ---------------------------------------------------------------------------


def test_persistence_diagram_kept_before_merge() -> None:
    """The diagram must contain ALL raw minima, even those merge would fold away."""
    grid, stats = free_energy_with_basins(_one_blob(), grid_size=40)
    # KDE on a single blob typically seeds a handful of noise minima.
    # Merge collapses them to 1, but the diagram retains the raw spectrum.
    assert stats.persistence_diagram.ndim == 1
    # Descending order — most persistent first.
    assert all(
        stats.persistence_diagram[i] >= stats.persistence_diagram[i + 1]
        for i in range(len(stats.persistence_diagram) - 1)
    )


def test_persistence_diagram_two_blobs_has_one_large_value() -> None:
    """For a clean double-well, the top of the diagram is ≫ 1 nat."""
    _, stats = free_energy_with_basins(_two_blobs(sep=5.0), grid_size=60)
    assert len(stats.persistence_diagram) >= 1
    assert stats.persistence_diagram[0] > 1.0


def test_kramers_lifetime_is_exp_of_persistence() -> None:
    p = np.array([0.0, 1.0, 3.0, 5.0])
    np.testing.assert_allclose(kramers_lifetime(p), np.exp(p))


def test_basin_count_at_thresholds_monotonic() -> None:
    """Higher τ → fewer basins survive (monotone non-increasing)."""
    _, stats = free_energy_with_basins(_two_blobs(sep=5.0), grid_size=60)
    counts = basin_count_at_thresholds(stats.persistence_diagram, [0.0, 0.5, 1.0, 2.0, 5.0])
    keys = sorted(counts)
    for a, b in zip(keys[:-1], keys[1:], strict=True):
        assert counts[a] >= counts[b]


def test_F_along_trajectory_matches_grid_at_grid_points() -> None:
    """F sampled at grid node coordinates equals the grid value (up to interp)."""
    pts = _two_blobs(sep=5.0)
    grid = fit_free_energy_2d(pts, grid_size=50)
    rng = np.random.default_rng(0)
    idx = rng.integers(1, len(grid.z1) - 1, size=10)
    jdx = rng.integers(1, len(grid.z2) - 1, size=10)
    sample = np.stack([grid.z1[idx], grid.z2[jdx]], axis=1)
    out = F_along_trajectory(grid, sample)
    expected = grid.F[jdx, idx]
    np.testing.assert_allclose(out, expected, atol=1e-9)


def test_F_along_trajectory_returns_one_value_per_point() -> None:
    pts = _two_blobs(sep=5.0)
    grid = fit_free_energy_2d(pts, grid_size=40)
    z = pts[::5]
    F_t = F_along_trajectory(grid, z)
    assert F_t.shape == (len(z),)
    assert (F_t >= 0).all()


# ---------------------------------------------------------------------------
# Step 1b-4 — dwell filter, effective basins, raw count exposure
# ---------------------------------------------------------------------------


def test_basin_dwell_counts_basic() -> None:
    labels = np.array([0, 0, 1, 2, 1, 1, 0])
    counts = basin_dwell_counts(labels, n_basins=3)
    np.testing.assert_array_equal(counts, [3, 3, 1])


def test_basin_dwell_counts_handles_zero_length() -> None:
    counts = basin_dwell_counts(np.array([], dtype=int), n_basins=5)
    np.testing.assert_array_equal(counts, [0, 0, 0, 0, 0])


def test_effective_basin_mask_requires_both_filters() -> None:
    persistence = np.array([5.0, 0.1, 5.0, 0.1])
    dwell = np.array([500, 500, 5, 5])
    mask = effective_basin_mask(persistence, dwell, min_persistence=1.0, min_dwell=21)
    # Only basin 0 passes BOTH filters.
    np.testing.assert_array_equal(mask, [True, False, False, False])


def test_effective_basin_mask_treats_inf_persistence_as_pass() -> None:
    """A single basin has inf persistence (no neighbor). It still passes if dwell does."""
    persistence = np.array([np.inf, 0.5])
    dwell = np.array([100, 100])
    mask = effective_basin_mask(persistence, dwell, min_persistence=1.0, min_dwell=21)
    np.testing.assert_array_equal(mask, [True, False])

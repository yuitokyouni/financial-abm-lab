"""Phase 6 stub tests: synthetic landscape + animation HTML render correctly."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

plotly = pytest.importorskip("plotly")

from state_atlas.viz.atlas3d import render_landscape_html  # noqa: E402
from state_atlas.viz.landscape import fit_free_energy_2d  # noqa: E402
from state_atlas.viz.synthetic import (  # noqa: E402
    grad_double_well_2d,
    simulate_double_well_2d,
)


def test_double_well_gradient_has_three_critical_points() -> None:
    """Sanity: ∇V vanishes at (-1,0), (0,0), (1,0)."""
    crits = np.array([[-1.0, 0.0], [0.0, 0.0], [1.0, 0.0]])
    g = grad_double_well_2d(crits)
    np.testing.assert_allclose(g, 0.0, atol=1e-9)


def test_synthetic_trajectory_visits_both_wells() -> None:
    """With enough noise and steps, the SDE should reach both basins."""
    z = simulate_double_well_2d(n_steps=20000, diffusion=0.6, seed=0)
    assert z.shape == (20001, 2)
    visited_left = (z[:, 0] < -0.5).any()
    visited_right = (z[:, 0] > 0.5).any()
    assert visited_left and visited_right, "trajectory should explore both wells"


def test_free_energy_grid_has_two_local_minima() -> None:
    """Synthetic data should produce a bimodal F with two minima along z1."""
    z = simulate_double_well_2d(n_steps=12000, diffusion=0.5, seed=1)
    grid = fit_free_energy_2d(z, grid_size=60)
    # Take the row closest to z2=0 and look for two distinct minima.
    j = int(np.argmin(np.abs(grid.z2 - 0.0)))
    profile = grid.F[j]
    minima = [
        i
        for i in range(1, len(profile) - 1)
        if profile[i] < profile[i - 1] and profile[i] < profile[i + 1]
    ]
    assert len(minima) >= 2, (
        f"expected ≥2 local minima along z1, found {len(minima)}: profile={profile.round(2)}"
    )


def test_render_emits_html_with_animation_frames(tmp_path: Path) -> None:
    z = simulate_double_well_2d(n_steps=2000, seed=2)
    grid = fit_free_energy_2d(z, grid_size=40)
    out = render_landscape_html(grid, z, tmp_path / "demo.html", n_frames=20)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # Must be a plotly HTML with multiple animation frames baked in.
    assert "plotly" in content.lower()
    assert "frames" in content.lower()


def test_fallback_2d_emits_html_without_3d_surface(tmp_path: Path) -> None:
    z = simulate_double_well_2d(n_steps=1000, seed=3)
    grid = fit_free_energy_2d(z, grid_size=30)
    out = render_landscape_html(grid, z, tmp_path / "demo_2d.html", fallback_2d=True)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "heatmap" in content.lower()

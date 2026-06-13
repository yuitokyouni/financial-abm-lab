"""Synthetic 2D Langevin trajectory for the Phase 6 visualization stub.

Generates a 2D over-damped Langevin path on a double-well potential
V(x, y) = (x² - 1)² + 0.5 * y², so the marginal in x has two wells at ±1
and the marginal in y is a single Gaussian. This gives a 2D analog of the
1D double well that ``market_dynamics.py`` already exercises, and is enough
to make the free-energy surface clearly bimodal in the demo HTML.
"""

from __future__ import annotations

import numpy as np


def grad_double_well_2d(z: np.ndarray) -> np.ndarray:
    """∇V where V(x, y) = (x²-1)² + 0.5 y². Returns shape (..., 2)."""
    x, y = z[..., 0], z[..., 1]
    dV_dx = 4 * x * (x**2 - 1)
    dV_dy = y
    return np.stack([dV_dx, dV_dy], axis=-1)


def simulate_double_well_2d(
    n_steps: int = 4000,
    dt: float = 0.02,
    diffusion: float = 0.25,
    z0: tuple[float, float] = (-1.0, 0.0),
    seed: int = 42,
) -> np.ndarray:
    """Over-damped Langevin: dz = -∇V dt + √(2D) dW. Returns (n_steps+1, 2)."""
    rng = np.random.default_rng(seed)
    z = np.empty((n_steps + 1, 2))
    z[0] = z0
    noise_scale = np.sqrt(2 * diffusion * dt)
    for k in range(n_steps):
        z[k + 1] = z[k] - grad_double_well_2d(z[k]) * dt + noise_scale * rng.standard_normal(2)
    return z

"""Phase 0 smoke tests: package imports, config loads with project invariants,
CLI help runs, and the pre-existing market_dynamics engine is reachable + runnable
in the new package location (it will be reused on z(t) in Phase 5).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from state_atlas import __version__
from state_atlas.cli import app
from state_atlas.config import load_config
from state_atlas.dynamics.market_dynamics import (
    MeanFieldLangevin,
    early_warning,
    estimate_drift_diffusion,
    grad_potential,
    potential,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_version_is_nonempty_string() -> None:
    assert isinstance(__version__, str) and __version__


def test_config_loads_and_holds_project_invariants() -> None:
    cfg = load_config(REPO_ROOT / "config.yaml")
    # Universe defaults from SPEC (overridable via config.yaml).
    assert cfg.universe.tickers == ["SPY", "TLT", "GLD", "DBC", "^VIX"]
    # CRITICAL invariant: latent_dim default = 2 so that F(z1, z2) is a 3D surface.
    # See DECISIONS.md (2026-05-30).
    assert cfg.embedding.latent_dim == 2
    # β-VAE default per DECISIONS.md.
    assert cfg.embedding.type == "vae"
    assert 0 < cfg.embedding.beta <= 1.0
    # CPU-only sizing: small MLP and modest epochs.
    assert cfg.embedding.hidden_dims == [64, 32]


def test_cli_help_runs() -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    out = res.stdout.lower()
    # All phase commands must be listed in the skeleton CLI.
    for cmd in ("data", "features", "embed", "atlas", "viz-demo", "backtest"):
        assert cmd in out, f"missing CLI command: {cmd}"


def test_cli_version_command() -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["version"])
    assert res.exit_code == 0
    assert __version__ in res.stdout


def test_existing_market_dynamics_engine_reusable_from_package() -> None:
    """SPEC §1: market_dynamics.py is reused on z(t) — must import + run here."""
    x = np.linspace(-2.0, 2.0, 11)
    v = potential(x, c=1.0)
    g = grad_potential(x, c=1.0)
    assert v.shape == x.shape and g.shape == x.shape
    # Double well at c=1: well minima at ±1 (lower than center x=0).
    assert v[5] > v[3] - 1e-9
    # tiny sim — just exercise the integrator end-to-end
    model = MeanFieldLangevin(N=8, dt=0.01, seed=0)
    sim = model.simulate(steps=5, c_fn=1.0)
    assert sim["X"].shape == (6, 8)
    assert sim["V"].shape == (6, 8)
    assert sim["t"].shape == (6,)


def test_km_and_ews_callable_for_future_latent_reuse() -> None:
    """Phase 5 will call these on z(t); confirm signature/contract still holds."""
    rng = np.random.default_rng(0)
    n, dt = 5_000, 0.01
    # OU-like series, just to exercise estimator paths.
    x = np.zeros(n)
    for k in range(n - 1):
        x[k + 1] = x[k] - 0.5 * x[k] * dt + np.sqrt(2 * 0.1 * dt) * rng.standard_normal()
    km = estimate_drift_diffusion(x, dt=dt, bins=30, min_count=10)
    assert set(km.keys()) >= {"x", "D1", "D2", "count"}
    ew = early_warning(x, window=500)
    assert set(ew.keys()) >= {"var", "ar1", "var_tau", "ar1_tau"}

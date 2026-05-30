"""Phase 6 (full) — end-to-end pipeline orchestrator.

Bundles the per-phase modules into a single ``run_atlas`` function so that
``atlas atlas`` and tests share the same entry point. The function is
deliberately small: each block is a one-line delegation to the phase module
that owns the logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from state_atlas.config import AtlasConfig
from state_atlas.data import MarketDataFrame, PriceSource, load_universe
from state_atlas.density import (
    BasinStats,
    FreeEnergyGrid,
    barrier_ratio,
    basin_count_at_thresholds,
    basin_dwell_counts,
    effective_basin_mask,
    free_energy_with_basins,
    kramers_lifetime,
)
from state_atlas.dynamics.latent_dynamics import (
    LatentDynamicsReport,
    analyze_latent_dynamics,
    label_points_on_grid,
)
from state_atlas.embedding import BetaVAEEmbedder
from state_atlas.features import FeatureSet, build_features

# Multi-threshold reading of the persistence diagram. None is privileged —
# the reader is supposed to look at the whole spectrum. These τ values just
# anchor a few interpretable points on it (e^τ ≈ regime half-life in days).
PERSISTENCE_THRESHOLDS: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0, 4.0)


@dataclass
class AtlasResult:
    mdf: MarketDataFrame
    features: FeatureSet
    embedder: BetaVAEEmbedder
    z: np.ndarray
    grid: FreeEnergyGrid | None
    stats: BasinStats | None
    dynamics: LatentDynamicsReport | None
    barrier_ratio: float
    # Catch 1 / 2 quantities surfaced at the top level so callers don't have
    # to dig into stats.persistence_diagram by hand.
    persistence_diagram: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    kramers_lifetimes: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    basin_counts_at_thresholds: dict[float, int] = field(default_factory=dict)
    d_eff_at_thresholds: dict[float, int] = field(default_factory=dict)
    d_eff_over_input_dim: dict[float, float] = field(default_factory=dict)
    # Dwell filter (Step 1b-4): a basin is "effective" only if the trajectory
    # actually visits it. Phantom KDE minima with dwell=0 don't count.
    point_labels: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    dwell_per_basin: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    effective_basin_mask_: np.ndarray = field(default_factory=lambda: np.array([], dtype=bool))
    raw_minima_count: int = 0

    @property
    def n_basins(self) -> int:
        return 0 if self.stats is None else self.stats.n_basins

    @property
    def n_effective_basins(self) -> int:
        """Basins surviving BOTH persistence (≥1.0) AND dwell (≥21d) filters."""
        return int(self.effective_basin_mask_.sum())


def run_atlas(
    cfg: AtlasConfig,
    *,
    source: PriceSource | None = None,
    mdf_override: MarketDataFrame | None = None,
    skip_dynamics: bool = False,
) -> AtlasResult:
    """data → features → β-VAE → F → basins → latent dynamics."""
    mdf = mdf_override if mdf_override is not None else load_universe(cfg, source=source)
    fs = build_features(mdf, cfg.features)
    X = fs.df.values.astype(np.float32)
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=cfg.embedding).fit(X)
    z = emb.transform(X)

    grid: FreeEnergyGrid | None = None
    stats: BasinStats | None = None
    dyn: LatentDynamicsReport | None = None
    br = 0.0
    pdiag = np.array([], dtype=float)
    lifetimes = np.array([], dtype=float)
    bcounts: dict[float, int] = {}
    point_labels = np.array([], dtype=int)
    dwell = np.array([], dtype=int)
    eff_mask = np.array([], dtype=bool)
    raw_minima_count = 0
    if z.shape[1] == 2:
        grid, stats = free_energy_with_basins(z, grid_size=cfg.density.grid_size)
        br = barrier_ratio(stats)
        pdiag = stats.persistence_diagram
        raw_minima_count = int(len(pdiag))
        lifetimes = kramers_lifetime(pdiag) if len(pdiag) else np.array([], dtype=float)
        bcounts = basin_count_at_thresholds(pdiag, PERSISTENCE_THRESHOLDS)
        point_labels = label_points_on_grid(z, grid, stats.labels)
        dwell = basin_dwell_counts(point_labels, stats.n_basins)
        eff_mask = effective_basin_mask(stats.persistence, dwell, min_persistence=1.0, min_dwell=21)
        if not skip_dynamics:
            dyn = analyze_latent_dynamics(
                z,
                grid,
                stats.labels,
                dt=1.0,
                km_bins=cfg.dynamics.km_bins,
                km_min_count=cfg.dynamics.km_min_count,
                ews_window=cfg.dynamics.ews_window,
            )

    # d_eff at the configured τ-sensitivity values, plus the dim-normalized form.
    taus = cfg.experiments.d_eff_tau_sensitivity or [cfg.experiments.d_eff_tau]
    d_eff = {float(t): emb.effective_dim(float(t)) for t in taus}
    in_dim = max(1, int(X.shape[1]))
    d_eff_norm = {t: d / in_dim for t, d in d_eff.items()}

    return AtlasResult(
        mdf=mdf,
        features=fs,
        embedder=emb,
        z=z,
        grid=grid,
        stats=stats,
        dynamics=dyn,
        barrier_ratio=br,
        persistence_diagram=pdiag,
        kramers_lifetimes=lifetimes,
        basin_counts_at_thresholds=bcounts,
        d_eff_at_thresholds=d_eff,
        d_eff_over_input_dim=d_eff_norm,
        point_labels=point_labels,
        dwell_per_basin=dwell,
        effective_basin_mask_=eff_mask,
        raw_minima_count=raw_minima_count,
    )


def report_to_json(result: AtlasResult, path: str | Path) -> Path:
    """Write a compact JSON summary of the atlas run.

    Persistence diagram, Kramers lifetimes, KL per dim, basin labels at the
    minima, and the d_eff / input_dim normalized values are all reported in
    full (no thresholded counts collapsing the measurement target).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n_transitions = 0 if result.dynamics is None else len(result.dynamics.transitions)
    payload: dict[str, object] = {
        "n_rows": int(len(result.z)),
        "input_dim": int(result.features.n_features),
        "latent_dim": int(result.z.shape[1]),
        "tickers": list(result.mdf.tickers),
        "n_basins_after_merge": int(result.n_basins),
        "barrier_ratio": float(result.barrier_ratio),
        "persistence_diagram": [float(x) for x in result.persistence_diagram.tolist()],
        "kramers_lifetimes_days": [float(x) for x in result.kramers_lifetimes.tolist()],
        "basin_counts_at_thresholds": {
            f"{t:.2f}": int(c) for t, c in result.basin_counts_at_thresholds.items()
        },
        "kl_per_dim": [float(x) for x in result.embedder.kl_per_dim.tolist()],
        "recon_mse": float(result.embedder.recon_mse),
        "d_eff_at_tau": {f"{t:.3f}": int(d) for t, d in result.d_eff_at_thresholds.items()},
        "d_eff_over_input_dim": {
            f"{t:.3f}": float(v) for t, v in result.d_eff_over_input_dim.items()
        },
        "n_basin_transitions": int(n_transitions),
        # Step 1b-4: dwell filter results, raw KDE-minima count, and the
        # honest "effective" basin count (persistence ≥1.0 ∧ dwell ≥21d).
        "raw_minima_count": int(result.raw_minima_count),
        "dwell_per_basin": [int(x) for x in result.dwell_per_basin.tolist()],
        "effective_basin_mask": [bool(x) for x in result.effective_basin_mask_.tolist()],
        "n_effective_basins": int(result.n_effective_basins),
        "caveat_kramers": (
            "kramers_lifetimes_days = exp(persistence) is UNCALIBRATED. "
            "Honest calibration requires latent D⁽²⁾ from Phase 5. A nominal "
            "lifetime exceeding the observation window is a sign the barrier "
            "is measured against a phantom KDE minimum, not a real regime."
        ),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return path


def render_atlas(result: AtlasResult, out: str | Path, *, fallback_2d: bool = False) -> Path:
    """Render the standalone HTML for ``result``. Uses the Phase 6 stub renderer."""
    from state_atlas.viz.atlas3d import render_landscape_html

    out = Path(out)
    if result.grid is None:
        raise RuntimeError(
            "Cannot render atlas: latent_dim != 2 (no 2D F grid). "
            "Use diagnostic mode (latent_dim=3) with a different renderer."
        )
    title = (
        "Market State Atlas  |  "
        f"basins={result.n_basins}  "
        f"barrier_ratio={result.barrier_ratio:.2f}  "
        f"d_eff(0.1)={result.embedder.effective_dim(0.1)}"
    )
    return render_landscape_html(result.grid, result.z, out, title=title, fallback_2d=fallback_2d)

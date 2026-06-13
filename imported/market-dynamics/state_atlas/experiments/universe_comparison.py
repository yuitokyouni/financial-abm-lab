"""Phase 4.5 — universe comparison meta-experiment.

For each candidate universe (config.yaml → experiments.universes), run the full
Phase 1-4 pipeline and record:

- ``d_eff(τ)`` for τ ∈ ``experiments.d_eff_tau_sensitivity``  (effective latent dim)
- ``n_basins`` after persistence merging
- ``barrier_ratio = mean(barrier) / mean(depth)``
- ``silhouette`` over basin labels (NaN when < 2 basins)

Outputs:
- ``artifacts/universe_comparison.csv``  (one row per universe)
- ``artifacts/universe_comparison.html`` (side-by-side F heatmaps + the metric table)

Pre-trained event flow guarantees: each universe gets its own cache file
(SPEC §4.5 design, DECISIONS.md). Re-runs are no-network if data is cached.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_score

from state_atlas.config import AtlasConfig
from state_atlas.data import MarketDataFrame, PriceSource, load_universe
from state_atlas.density import (
    BasinStats,
    FreeEnergyGrid,
    barrier_ratio,
    free_energy_with_basins,
)
from state_atlas.embedding import BetaVAEEmbedder
from state_atlas.features import build_features


@dataclass
class UniverseReport:
    universe_id: str
    tickers: list[str]
    n_rows: int
    n_features: int
    d_eff: dict[float, int]  # τ → effective dim
    kl_per_dim: list[float]
    recon_mse: float
    n_basins: int
    barrier_ratio: float
    silhouette: float
    # Carried for the side-by-side HTML render. Not in CSV.
    grid: FreeEnergyGrid | None = None
    stats: BasinStats | None = None
    z: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))


def _label_points(z: np.ndarray, grid: FreeEnergyGrid, label_grid: np.ndarray) -> np.ndarray:
    """Assign each (z1, z2) point to the basin label of its nearest grid cell."""
    ix = np.clip(np.searchsorted(grid.z1, z[:, 0]) - 1, 0, len(grid.z1) - 1)
    iy = np.clip(np.searchsorted(grid.z2, z[:, 1]) - 1, 0, len(grid.z2) - 1)
    return label_grid[iy, ix]


def run_one_universe(
    universe_id: str,
    tickers: list[str],
    cfg: AtlasConfig,
    source: PriceSource | None = None,
    mdf_override: MarketDataFrame | None = None,
) -> UniverseReport:
    """Run Phase 1-4 on a single universe and gather metrics.

    ``mdf_override`` is the test injection point (skip data fetch entirely).
    """
    cfg_uni = cfg.model_copy(deep=True)
    cfg_uni.universe.tickers = list(tickers)
    if mdf_override is not None:
        mdf = mdf_override
    else:
        mdf = load_universe(cfg_uni, source=source)

    fs = build_features(mdf, cfg_uni.features)
    X = fs.df.values.astype(np.float32)
    if len(X) < 64:
        raise RuntimeError(
            f"{universe_id}: only {len(X)} feature rows after warm-up — too short for VAE training"
        )

    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=cfg_uni.embedding).fit(X)
    z = emb.transform(X)

    taus = cfg_uni.experiments.d_eff_tau_sensitivity or [cfg_uni.experiments.d_eff_tau]
    d_eff = {float(t): emb.effective_dim(float(t)) for t in taus}

    grid: FreeEnergyGrid | None = None
    stats: BasinStats | None = None
    n_basins = 0
    br = 0.0
    sil = float("nan")
    if z.shape[1] == 2:
        grid, stats = free_energy_with_basins(z, grid_size=cfg_uni.density.grid_size)
        n_basins = stats.n_basins
        br = barrier_ratio(stats)
        point_labels = _label_points(z, grid, stats.labels)
        if n_basins >= 2 and len(set(point_labels.tolist())) >= 2:
            sil = float(silhouette_score(z, point_labels))

    return UniverseReport(
        universe_id=universe_id,
        tickers=list(tickers),
        n_rows=int(len(z)),
        n_features=int(X.shape[1]),
        d_eff=d_eff,
        kl_per_dim=emb.kl_per_dim.tolist(),
        recon_mse=float(emb.recon_mse),
        n_basins=int(n_basins),
        barrier_ratio=float(br),
        silhouette=sil,
        grid=grid,
        stats=stats,
        z=z,
    )


def run_all(
    cfg: AtlasConfig,
    source: PriceSource | None = None,
    subset: list[str] | None = None,
) -> dict[str, UniverseReport]:
    out: dict[str, UniverseReport] = {}
    for uid, tickers in cfg.experiments.universes.items():
        if subset is not None and uid not in subset:
            continue
        out[uid] = run_one_universe(uid, tickers, cfg, source=source)
    return out


def write_csv(reports: dict[str, UniverseReport], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for r in reports.values():
        row: dict[str, object] = {
            "universe_id": r.universe_id,
            "tickers": ",".join(r.tickers),
            "n_rows": r.n_rows,
            "n_features": r.n_features,
            "recon_mse": round(r.recon_mse, 6),
            "n_basins": r.n_basins,
            "barrier_ratio": round(r.barrier_ratio, 4),
            "silhouette": (round(r.silhouette, 4) if not np.isnan(r.silhouette) else ""),
            "kl_per_dim": ",".join(f"{k:.4f}" for k in r.kl_per_dim),
        }
        for tau, d in sorted(r.d_eff.items()):
            row[f"d_eff_tau_{tau}"] = d
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_html(reports: dict[str, UniverseReport], path: str | Path) -> Path:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = len(reports)
    if n == 0:
        path.write_text("<html><body>No reports.</body></html>", encoding="utf-8")
        return path

    fig = make_subplots(
        rows=1,
        cols=n,
        subplot_titles=[
            f"{r.universe_id}  |  basins={r.n_basins}  ratio={r.barrier_ratio:.2f}"
            for r in reports.values()
        ],
    )
    for k, (_uid, r) in enumerate(reports.items()):
        if r.grid is None:
            continue
        fig.add_trace(
            go.Heatmap(
                x=r.grid.z1,
                y=r.grid.z2,
                z=r.grid.F,
                colorscale="Viridis",
                showscale=(k == n - 1),
                colorbar={"title": "F(z)"} if k == n - 1 else None,
            ),
            row=1,
            col=k + 1,
        )
    fig.update_layout(
        title="Universe comparison — free energy F(z)",
        height=500,
        width=300 * n,
    )

    table_rows = []
    table_rows.append(
        "<tr><th>id</th><th>tickers</th><th>rows</th><th>features</th>"
        "<th>d_eff</th><th>basins</th><th>barrier_ratio</th><th>silhouette</th></tr>"
    )
    for r in reports.values():
        d_eff_str = " | ".join(f"τ={t}:{d}" for t, d in sorted(r.d_eff.items()))
        sil_str = "—" if np.isnan(r.silhouette) else f"{r.silhouette:.3f}"
        table_rows.append(
            f"<tr><td>{r.universe_id}</td><td>{', '.join(r.tickers)}</td>"
            f"<td>{r.n_rows}</td><td>{r.n_features}</td>"
            f"<td>{d_eff_str}</td><td>{r.n_basins}</td>"
            f"<td>{r.barrier_ratio:.3f}</td><td>{sil_str}</td></tr>"
        )
    table_html = (
        "<h2>Phase 4.5 — Universe comparison metrics</h2>"
        "<table border='1' cellpadding='4' cellspacing='0' "
        "style='border-collapse:collapse;font-family:monospace'>" + "".join(table_rows) + "</table>"
    )

    body = fig.to_html(include_plotlyjs="cdn", full_html=False)
    full = (
        "<html><head><meta charset='utf-8'><title>Universe comparison</title></head>"
        f"<body>{body}{table_html}</body></html>"
    )
    path.write_text(full, encoding="utf-8")
    return path

"""Phase 7 — walk-forward backtest with permutation null.

Scope (per SPEC §6 Phase 7): does the basin label of z(t) carry **predictive**
information about the benchmark's forward realized volatility? We keep the
scope deliberately narrow:

- a single chronological train/test split (train_frac of features) — this is
  the smallest walk-forward step that does not leak; longer rolling windows
  are easy to layer on top later.
- VAE + F + basins fitted on TRAIN ONLY. Test points get basin labels by
  projecting through the *train-fitted* embedder and grid.
- forward realized vol of the benchmark (default = first ticker) computed
  *strictly after* each test point, using future close prices that the
  embedder never saw.
- statistical test = one-way ANOVA across basins; null = permutation of
  basin labels within the same test sample (so any difference must come
  from the labels, not the marginal distribution of forward vol).

The report returns ``edge_detected`` along with the F statistic, ANOVA p, and
the 95th percentile of the permutation null. The default phrasing is
"no edge"; the bar to flip it is intentionally high — SPEC §2-6 says we MUST
treat "no edge" as a legitimate outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import stats as scistats

from state_atlas.config import AtlasConfig
from state_atlas.data.base import MarketDataFrame
from state_atlas.density import free_energy_with_basins
from state_atlas.dynamics.latent_dynamics import label_points_on_grid
from state_atlas.embedding import BetaVAEEmbedder
from state_atlas.features import build_features


@dataclass
class BacktestReport:
    n_train: int
    n_test: int
    n_test_valid: int
    n_basins: int
    forward_days: int
    benchmark: str
    basin_forward_vol: dict[int, float] = field(default_factory=dict)
    basin_test_count: dict[int, int] = field(default_factory=dict)
    pooled_vol: float = float("nan")
    f_stat: float = float("nan")
    p_value: float = float("nan")
    null_f_95: float = float("nan")
    edge_detected: bool = False
    summary: str = ""


def single_split_backtest(
    mdf: MarketDataFrame,
    cfg: AtlasConfig,
    *,
    train_frac: float = 0.7,
    forward_days: int = 21,
    benchmark_ticker: str | None = None,
    n_permutations: int = 200,
    rng_seed: int = 0,
) -> BacktestReport:
    """Run the single-split backtest described in the module docstring."""
    fs = build_features(mdf, cfg.features)
    n = len(fs.df)
    if n < 200:
        raise RuntimeError(
            f"backtest needs ≥200 feature rows, got {n} — universe / range too short"
        )
    if cfg.embedding.latent_dim != 2:
        raise RuntimeError(
            f"backtest requires latent_dim=2 for basin assignment, got {cfg.embedding.latent_dim}"
        )

    benchmark = benchmark_ticker or mdf.tickers[0]
    n_train = int(n * train_frac)
    train_idx = fs.df.index[:n_train]
    test_idx = fs.df.index[n_train:]

    X_train = fs.df.loc[train_idx].values.astype(np.float32)
    X_test = fs.df.loc[test_idx].values.astype(np.float32)

    # Fit Phase 3-4 on TRAIN ONLY — strict no leakage.
    emb = BetaVAEEmbedder(in_dim=X_train.shape[1], cfg=cfg.embedding).fit(X_train)
    z_train = emb.transform(X_train)
    z_test = emb.transform(X_test)
    grid, stats = free_energy_with_basins(z_train, grid_size=cfg.density.grid_size)
    test_labels = label_points_on_grid(z_test, grid, stats.labels)

    # Forward realized vol on the benchmark — uses prices the embedder never saw.
    close = mdf.df[(benchmark, "close")].astype(float)
    log_close = np.log(close)
    daily_ret = log_close.diff(1)
    full_index = mdf.df.index

    forward_vols = np.full(len(test_idx), np.nan)
    for i, date in enumerate(test_idx):
        try:
            pos = full_index.get_loc(date)
        except KeyError:
            continue
        if pos + 1 + forward_days >= len(full_index):
            continue
        window = daily_ret.iloc[pos + 1 : pos + 1 + forward_days]
        if window.isna().any():
            continue
        forward_vols[i] = float(window.std())

    valid = ~np.isnan(forward_vols)
    if valid.sum() < 30:
        return BacktestReport(
            n_train=n_train,
            n_test=len(test_idx),
            n_test_valid=int(valid.sum()),
            n_basins=stats.n_basins,
            forward_days=forward_days,
            benchmark=benchmark,
            summary=(
                f"not enough valid test points ({int(valid.sum())}) "
                f"to evaluate edge — report skipped"
            ),
        )

    labels_v = test_labels[valid]
    vols_v = forward_vols[valid]

    groups: dict[int, np.ndarray] = {}
    for k in range(stats.n_basins):
        g = vols_v[labels_v == k]
        if len(g) >= 5:
            groups[k] = g

    if len(groups) < 2:
        return BacktestReport(
            n_train=n_train,
            n_test=len(test_idx),
            n_test_valid=int(valid.sum()),
            n_basins=stats.n_basins,
            forward_days=forward_days,
            benchmark=benchmark,
            pooled_vol=float(vols_v.mean()),
            basin_forward_vol={k: float(g.mean()) for k, g in groups.items()},
            basin_test_count={k: int(len(g)) for k, g in groups.items()},
            summary=(
                "<2 basins reached in test window — cannot run ANOVA; "
                "report no edge by construction"
            ),
        )

    f_stat, p_value = scistats.f_oneway(*groups.values())

    # Permutation null: shuffle labels among the same test points, redo ANOVA.
    rng = np.random.default_rng(rng_seed)
    null_f: list[float] = []
    label_arr = labels_v.copy()
    n_basins = int(stats.n_basins)
    for _ in range(n_permutations):
        shuffled = rng.permutation(label_arr)
        ng = []
        for k in range(n_basins):
            g = vols_v[shuffled == k]
            if len(g) >= 5:
                ng.append(g)
        if len(ng) >= 2:
            f, _ = scistats.f_oneway(*ng)
            if np.isfinite(f):
                null_f.append(float(f))

    null_f_95 = float(np.percentile(null_f, 95)) if null_f else float("nan")
    edge = bool(
        np.isfinite(f_stat)
        and np.isfinite(null_f_95)
        and f_stat > null_f_95
        and np.isfinite(p_value)
        and p_value < 0.05
    )

    if edge:
        summary = (
            f"edge detected: basin label predicts forward {forward_days}d vol "
            f"of {benchmark} (F={f_stat:.2f}, p={p_value:.3g}, 95th null F={null_f_95:.2f})"
        )
    else:
        summary = (
            f"no edge: basin label does not significantly predict forward "
            f"{forward_days}d vol of {benchmark} "
            f"(F={f_stat:.2f}, p={p_value:.3g}, 95th null F={null_f_95:.2f})"
        )

    return BacktestReport(
        n_train=n_train,
        n_test=len(test_idx),
        n_test_valid=int(valid.sum()),
        n_basins=stats.n_basins,
        forward_days=forward_days,
        benchmark=benchmark,
        basin_forward_vol={k: float(g.mean()) for k, g in groups.items()},
        basin_test_count={k: int(len(g)) for k, g in groups.items()},
        pooled_vol=float(vols_v.mean()),
        f_stat=float(f_stat),
        p_value=float(p_value),
        null_f_95=null_f_95,
        edge_detected=edge,
        summary=summary,
    )


def write_report(report: BacktestReport, path: str | Path) -> Path:
    """Write a small human-readable report file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Backtest report (Phase 7) — benchmark={report.benchmark}",
        f"  train rows = {report.n_train}",
        f"  test rows  = {report.n_test} (valid={report.n_test_valid})",
        f"  basins     = {report.n_basins}",
        f"  forward_days = {report.forward_days}",
        f"  pooled_forward_vol = {report.pooled_vol:.6f}",
        f"  F_stat = {report.f_stat:.4f}  p = {report.p_value:.4g}  "
        f"95th null F = {report.null_f_95:.4f}",
        "  basin_forward_vol:",
    ]
    for k, v in sorted(report.basin_forward_vol.items()):
        n = report.basin_test_count.get(k, 0)
        lines.append(f"    basin {k}: vol={v:.6f}  n={n}")
    lines.append("")
    lines.append(f"VERDICT: {report.summary}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

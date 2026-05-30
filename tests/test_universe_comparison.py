"""Phase 4.5 — universe comparison runs end-to-end on synthetic mocked data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from state_atlas.config import AtlasConfig, load_config
from state_atlas.data.base import OHLCV_FIELDS, MarketDataFrame
from state_atlas.experiments.universe_comparison import (
    UniverseReport,
    run_one_universe,
    write_csv,
    write_html,
)

torch = pytest.importorskip("torch")

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_mdf(tickers: list[str], n_days: int = 800, seed: int = 0) -> MarketDataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-02", periods=n_days)
    data = {}
    for t in tickers:
        base = 100 * np.exp(np.cumsum(rng.standard_normal(n_days) * 0.01))
        for f in ("open", "high", "low", "close", "adj_close"):
            data[(t, f)] = base + rng.standard_normal(n_days) * 0.05
        data[(t, "volume")] = (
            np.zeros(n_days)
            if t == "^VIX"
            else rng.integers(1_000_000, 5_000_000, size=n_days).astype(float)
        )
    cols = [(t, f) for t in tickers for f in OHLCV_FIELDS]
    df = pd.DataFrame({c: data[c] for c in cols}, index=idx)
    df.columns = pd.MultiIndex.from_tuples(cols)
    return MarketDataFrame(df=df, has_volume={t: t != "^VIX" for t in tickers})


def _short_cfg() -> AtlasConfig:
    cfg = load_config(REPO_ROOT / "config.yaml")
    # Keep VAE training short for the test.
    cfg.embedding.epochs = 20
    cfg.embedding.kl_anneal_epochs = 10
    cfg.embedding.batch_size = 64
    cfg.embedding.hidden_dims = [16, 8]
    cfg.density.grid_size = 30
    return cfg


def test_run_one_universe_smoke_aw() -> None:
    cfg = _short_cfg()
    tickers = ["SPY", "TLT", "GLD", "DBC", "^VIX"]
    mdf = _make_mdf(tickers, n_days=800)
    r = run_one_universe("aw", tickers, cfg, mdf_override=mdf)
    assert isinstance(r, UniverseReport)
    assert r.universe_id == "aw"
    assert r.n_rows > 100
    assert r.n_features == 27  # SPEC §4: 5×3 + 5 + 4 + 1 + 2
    assert r.grid is not None and r.grid.F.shape == (cfg.density.grid_size,) * 2
    # All sensitivity τ values should produce an int dim in [0, latent_dim].
    for tau, d in r.d_eff.items():
        assert 0 <= d <= cfg.embedding.latent_dim, (tau, d)
    # KL per dim has the right length.
    assert len(r.kl_per_dim) == cfg.embedding.latent_dim


def test_run_one_universe_smoke_equity_sectors() -> None:
    """Equity-only universe runs without crashing even when no ^VIX present."""
    cfg = _short_cfg()
    tickers = ["SPY", "QQQ", "IWM", "XLF", "XLE"]
    mdf = _make_mdf(tickers, n_days=800)
    r = run_one_universe("equity_sectors", tickers, cfg, mdf_override=mdf)
    # 5×3 ret + 5 rv + 5 vol_z + 1 disp (no VIX features)
    assert r.n_features == 26
    assert r.n_basins >= 1


def test_silhouette_is_nan_when_single_basin() -> None:
    cfg = _short_cfg()
    tickers = ["SPY", "TLT"]
    mdf = _make_mdf(tickers, n_days=800)
    r = run_one_universe("tiny", tickers, cfg, mdf_override=mdf)
    if r.n_basins < 2:
        assert np.isnan(r.silhouette)


def test_csv_and_html_emitted(tmp_path: Path) -> None:
    cfg = _short_cfg()
    tickers = ["SPY", "TLT", "GLD"]
    mdf = _make_mdf(tickers, n_days=800)
    reports = {"aw_lite": run_one_universe("aw_lite", tickers, cfg, mdf_override=mdf)}
    csv_path = write_csv(reports, tmp_path / "uc.csv")
    html_path = write_html(reports, tmp_path / "uc.html")
    assert csv_path.exists() and html_path.exists()
    df = pd.read_csv(csv_path)
    assert "universe_id" in df.columns
    assert "barrier_ratio" in df.columns
    for tau in cfg.experiments.d_eff_tau_sensitivity:
        assert f"d_eff_tau_{tau}" in df.columns
    html_text = html_path.read_text(encoding="utf-8")
    assert "plotly" in html_text.lower()
    assert "Universe comparison" in html_text

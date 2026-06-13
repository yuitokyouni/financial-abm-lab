"""Phase 7 — backtest smoke + honest-reporting tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from state_atlas.config import AtlasConfig, load_config
from state_atlas.data.base import OHLCV_FIELDS, MarketDataFrame

pytest.importorskip("torch")

from state_atlas.backtest import (  # noqa: E402
    BacktestReport,
    single_split_backtest,
    write_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _mdf(tickers: list[str], n_days: int = 1200, seed: int = 0) -> MarketDataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2016-01-04", periods=n_days)
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
    cfg.embedding.epochs = 15
    cfg.embedding.kl_anneal_epochs = 5
    cfg.embedding.hidden_dims = [16, 8]
    cfg.density.grid_size = 25
    return cfg


def test_backtest_returns_report_with_summary_string() -> None:
    cfg = _short_cfg()
    mdf = _mdf(["SPY", "TLT", "GLD", "DBC", "^VIX"])
    rep = single_split_backtest(mdf, cfg, n_permutations=50)
    assert isinstance(rep, BacktestReport)
    assert isinstance(rep.summary, str) and len(rep.summary) > 0
    assert rep.n_train > 0
    assert rep.n_test > 0
    assert rep.n_basins >= 1


def test_random_features_default_to_no_edge() -> None:
    """On pure random data we MUST not claim an edge — SPEC §8 forbids it."""
    cfg = _short_cfg()
    cfg.embedding.epochs = 10
    mdf = _mdf(["SPY", "TLT", "GLD"], n_days=1200, seed=42)
    rep = single_split_backtest(mdf, cfg, n_permutations=100, rng_seed=1)
    # If the backtest accidentally finds an "edge" on random data, that's the
    # multiple-comparisons / look-ahead bug we want to catch.
    assert not rep.edge_detected, (
        f"Spurious edge on random features: {rep.summary}\n"
        f"F={rep.f_stat}  p={rep.p_value}  null_F_95={rep.null_f_95}"
    )
    assert "no edge" in rep.summary or "cannot run ANOVA" in rep.summary


def test_write_report_emits_file(tmp_path: Path) -> None:
    cfg = _short_cfg()
    mdf = _mdf(["SPY", "TLT", "GLD"])
    rep = single_split_backtest(mdf, cfg, n_permutations=20)
    out = write_report(rep, tmp_path / "br.txt")
    text = out.read_text(encoding="utf-8")
    assert "VERDICT:" in text
    assert "F_stat" in text


def test_too_short_universe_raises() -> None:
    cfg = _short_cfg()
    mdf = _mdf(["SPY", "TLT"], n_days=260)  # ~260 days < 252 + buffer
    with pytest.raises(RuntimeError, match="≥200|too short"):
        single_split_backtest(mdf, cfg)

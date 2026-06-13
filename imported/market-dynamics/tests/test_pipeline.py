"""Phase 6 (full) — end-to-end pipeline produces an HTML atlas."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from state_atlas.config import AtlasConfig, load_config
from state_atlas.data.base import OHLCV_FIELDS, MarketDataFrame

pytest.importorskip("torch")
pytest.importorskip("plotly")

from state_atlas.pipeline import render_atlas, run_atlas  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def _mdf(tickers: list[str], n_days: int = 800, seed: int = 0) -> MarketDataFrame:
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
    cfg.embedding.epochs = 15
    cfg.embedding.kl_anneal_epochs = 5
    cfg.embedding.hidden_dims = [16, 8]
    cfg.density.grid_size = 25
    cfg.dynamics.km_bins = 20
    cfg.dynamics.km_min_count = 10
    cfg.dynamics.ews_window = 100
    return cfg


def test_pipeline_runs_and_renders_html(tmp_path: Path) -> None:
    cfg = _short_cfg()
    tickers = ["SPY", "TLT", "GLD", "DBC", "^VIX"]
    mdf = _mdf(tickers)
    result = run_atlas(cfg, mdf_override=mdf)
    assert result.grid is not None
    assert result.stats is not None
    assert result.dynamics is not None
    assert len(result.dynamics.km_per_axis) == 2
    # Catch 1: persistence diagram and Kramers lifetimes surfaced at top level.
    assert result.persistence_diagram.ndim == 1
    assert result.kramers_lifetimes.shape == result.persistence_diagram.shape
    assert len(result.basin_counts_at_thresholds) > 0
    # Catch 2: d_eff / input_dim is reported alongside raw d_eff.
    for tau, d in result.d_eff_at_thresholds.items():
        assert 0 <= d <= cfg.embedding.latent_dim
        assert 0 <= result.d_eff_over_input_dim[tau] <= 1.0
    out = render_atlas(result, tmp_path / "atlas.html")
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "plotly" in html.lower()
    assert "Market State Atlas" in html


def test_report_to_json_emits_persistence_spectrum(tmp_path: Path) -> None:
    import json as _json

    from state_atlas.pipeline import report_to_json

    cfg = _short_cfg()
    mdf = _mdf(["SPY", "TLT", "GLD"])
    result = run_atlas(cfg, mdf_override=mdf, skip_dynamics=True)
    out = report_to_json(result, tmp_path / "atlas_report.json")
    payload = _json.loads(out.read_text(encoding="utf-8"))
    assert "persistence_diagram" in payload
    assert "kramers_lifetimes_days" in payload
    assert "basin_counts_at_thresholds" in payload
    assert "d_eff_over_input_dim" in payload
    assert isinstance(payload["persistence_diagram"], list)


def test_pipeline_skip_dynamics_flag(tmp_path: Path) -> None:
    cfg = _short_cfg()
    tickers = ["SPY", "TLT", "GLD"]
    mdf = _mdf(tickers)
    result = run_atlas(cfg, mdf_override=mdf, skip_dynamics=True)
    assert result.dynamics is None
    # render still works
    out = render_atlas(result, tmp_path / "atlas2.html")
    assert out.exists()


def test_pipeline_fallback_2d_html(tmp_path: Path) -> None:
    cfg = _short_cfg()
    mdf = _mdf(["SPY", "TLT", "GLD"])
    result = run_atlas(cfg, mdf_override=mdf, skip_dynamics=True)
    out = render_atlas(result, tmp_path / "atlas_2d.html", fallback_2d=True)
    html = out.read_text(encoding="utf-8")
    assert "heatmap" in html.lower()

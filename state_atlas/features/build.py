"""Construct the causal feature matrix.

Every column is built so that the value at time t depends only on prices ≤ t.
The build_features function is the only path from raw OHLCV to the FeatureSet
consumed by the embedding — Phase 2's leakage tests exercise it directly.

Causal standardization: each column is rolling-z-scored with a past-only window
(``causal_zscore_window_days``). Rows where any column is still in warm-up
(NaN) are dropped at the very end, so the returned frame has no NaN.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from state_atlas.config import FeaturesConfig
from state_atlas.data.base import MarketDataFrame
from state_atlas.features.contract import FeatureSet, expected_feature_columns


def _log_return(close: pd.Series, horizon: int) -> pd.Series:
    return np.log(close).diff(horizon)


def _realized_vol(close: pd.Series, window: int) -> pd.Series:
    r1 = np.log(close).diff(1)
    return r1.rolling(window=window, min_periods=window).std()


def _volume_zscore(volume: pd.Series, window: int) -> pd.Series:
    # log1p stabilizes the heavy-tailed daily volume.
    v = np.log1p(volume.clip(lower=0))
    mu = v.rolling(window=window, min_periods=window).mean()
    sd = v.rolling(window=window, min_periods=window).std()
    return (v - mu) / sd.replace(0, np.nan)


def _causal_zscore(s: pd.Series, window: int) -> pd.Series:
    mu = s.rolling(window=window, min_periods=window).mean()
    sd = s.rolling(window=window, min_periods=window).std()
    return (s - mu) / sd.replace(0, np.nan)


def build_features(
    mdf: MarketDataFrame,
    cfg: FeaturesConfig,
    vix_ticker: str = "^VIX",
) -> FeatureSet:
    """Build the (causal) FeatureSet. See contract.py for the column schema."""
    tickers = mdf.tickers
    df = mdf.df
    has_vol = mdf.has_volume

    raw: dict[str, pd.Series] = {}

    # log returns per asset per horizon
    for t in tickers:
        close = df[(t, "close")].astype(float)
        for h in cfg.return_horizons_days:
            raw[f"ret_{h}d__{t}"] = _log_return(close, h)

    # realized vol (21d default), per asset
    for t in tickers:
        close = df[(t, "close")].astype(float)
        raw[f"rv_21d__{t}"] = _realized_vol(close, cfg.realized_vol_window_days)

    # volume z-score only for tickers with real volume
    for t in tickers:
        if has_vol.get(t, False):
            vol = df[(t, "volume")].astype(float)
            raw[f"vol_z_63d__{t}"] = _volume_zscore(vol, cfg.volume_zscore_window_days)

    # cross-sectional dispersion of 1d log returns — only meaningful with ≥2 assets.
    if len(tickers) >= 2:
        r1 = pd.DataFrame({t: np.log(df[(t, "close")].astype(float)).diff(1) for t in tickers})
        raw["cs_dispersion_1d"] = r1.std(axis=1)

    # VIX level + 5d change (if present)
    if vix_ticker in tickers:
        vix_close = df[(vix_ticker, "close")].astype(float)
        raw[f"level__{vix_ticker}"] = vix_close
        raw[f"chg_5d__{vix_ticker}"] = vix_close.diff(5)

    feat_raw = pd.DataFrame(raw, index=df.index)

    # Causal rolling z-score on every column (past-only).
    w = cfg.causal_zscore_window_days
    feat_z = feat_raw.apply(lambda s: _causal_zscore(s, w))

    # Enforce deterministic column order from contract.py.
    expected = expected_feature_columns(
        tickers=tickers,
        has_volume=has_vol,
        horizons=cfg.return_horizons_days,
        include_vix=(vix_ticker in tickers),
        vix_ticker=vix_ticker,
    )
    missing = [c for c in expected if c not in feat_z.columns]
    if missing:
        raise RuntimeError(f"feature build missing expected columns: {missing}")
    feat_z = feat_z[expected]

    # Drop warm-up rows: any NaN means at least one rolling window hasn't filled yet.
    feat_z = feat_z.dropna(how="any")

    return FeatureSet(df=feat_z, columns=expected, tickers=tickers)

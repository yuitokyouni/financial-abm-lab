"""Feature schema — single source of truth for what enters the embedding.

A FeatureSet is a DataFrame whose:
  * index    = causal timestamps (a strict subset of the price index, no look-ahead)
  * columns  = stable, deterministic column names (this module is the only place
               where those names are defined)
  * values   = rolling-zscored real numbers, no NaN inside the window after warm-up

Phase 3 (β-VAE) treats columns as exchangeable feature dimensions but the order
is deterministic so reload/transform stays meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FeatureSet:
    df: pd.DataFrame
    columns: list[str]
    tickers: list[str]

    @property
    def n_features(self) -> int:
        return len(self.columns)


def expected_feature_columns(
    tickers: list[str],
    has_volume: dict[str, bool],
    horizons: list[int],
    include_vix: bool = True,
    vix_ticker: str = "^VIX",
) -> list[str]:
    """Return the deterministic, ordered list of feature column names.

    Order: per-asset return horizons, per-asset realized vol, per-asset volume z-score
    (only for tickers with has_volume=True), cross-sectional dispersion (only if
    ≥2 tickers), optional VIX level + 5d change.
    """
    cols: list[str] = []
    for t in tickers:
        for h in horizons:
            cols.append(f"ret_{h}d__{t}")
    for t in tickers:
        cols.append(f"rv_21d__{t}")
    for t in tickers:
        if has_volume.get(t, False):
            cols.append(f"vol_z_63d__{t}")
    if len(tickers) >= 2:
        cols.append("cs_dispersion_1d")
    if include_vix and vix_ticker in tickers:
        cols.append(f"level__{vix_ticker}")
        cols.append(f"chg_5d__{vix_ticker}")
    return cols

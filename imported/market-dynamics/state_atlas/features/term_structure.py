"""VIX term-structure helpers — order parameter for the vol-complex atlas.

term_slope = log(VIX3M / VIX)
  > 0 : contango  (long end > spot)   = quiet, vol carry positive
  < 0 : backwardation (spot > long)   = stress, vol carry negative

This is a textbook order parameter for the volatility regime. It is *not*
mixed into the 30-dim feature matrix that goes through the β-VAE — it is
used directly as one axis of the free-energy surface, alongside log(VIX).
See DECISIONS.md ("direct topography on known order parameters") for the
rationale; the short version is that the VAE is a 27-D → 2-D lossy
compressor (recon_mse ≈ 0.74), and burying the regime-defining axis inside
that compressor risks false negatives.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from state_atlas.data.base import MarketDataFrame


def compute_vix_order_parameters(
    mdf: MarketDataFrame,
    short_ticker: str = "^VIX",
    long_ticker: str = "^VIX3M",
) -> pd.DataFrame:
    """Return a DataFrame with ``log_vix`` and ``term_slope`` indexed by date.

    ``log_vix`` is the natural log of the spot index (scale-comparable to
    ``term_slope``). ``term_slope`` is ``log(long / short)``, scale-free.

    Rows where either VIX or VIX3M is NaN (e.g. early data before VIX3M's
    2014-01 launch) are dropped — the caller decides whether to feed the
    cleaned frame straight into the KDE or window it further.
    """
    for t in (short_ticker, long_ticker):
        if t not in mdf.tickers:
            raise ValueError(f"term-structure needs '{t}' in the universe, got {mdf.tickers}")
    short_close = mdf.df[(short_ticker, "close")].astype(float)
    long_close = mdf.df[(long_ticker, "close")].astype(float)
    log_vix = np.log(short_close)
    term_slope = np.log(long_close / short_close)
    df = pd.DataFrame(
        {"log_vix": log_vix, "term_slope": term_slope},
        index=mdf.df.index,
    ).dropna(how="any")
    return df


def order_parameter_array(order_df: pd.DataFrame) -> np.ndarray:
    """Convenience: DataFrame → (N, 2) array in the order expected by KDE."""
    return order_df[["log_vix", "term_slope"]].to_numpy(dtype=float)

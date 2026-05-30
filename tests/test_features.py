"""Phase 2 — causal feature matrix + leakage guard.

The marquee test is ``test_no_lookahead_under_future_corruption``: we build
the feature matrix on a series, then *replace all values after a cut point T*
with random noise, rebuild, and assert that every feature value at times t ≤ T
is identical. If any feature peeks into the future, perturbing the future
changes the past and the test fails.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from state_atlas.config import FeaturesConfig
from state_atlas.data.base import OHLCV_FIELDS, MarketDataFrame
from state_atlas.features import build_features, expected_feature_columns

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

DEFAULT_FEATURES_CFG = FeaturesConfig(
    return_horizons_days=[1, 5, 21],
    realized_vol_window_days=21,
    volume_zscore_window_days=63,
    causal_zscore_window_days=252,
)


def _synth_mdf(
    tickers: list[str],
    n_days: int = 600,
    with_vix: bool = True,
    seed: int = 0,
) -> MarketDataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-02", periods=n_days)
    data: dict[tuple[str, str], np.ndarray] = {}
    for t in tickers:
        base = 100 * np.exp(np.cumsum(rng.standard_normal(n_days) * 0.01))
        for f in ("open", "high", "low", "close", "adj_close"):
            data[(t, f)] = base + rng.standard_normal(n_days) * 0.05
        if t == "^VIX" and with_vix:
            data[(t, "volume")] = np.zeros(n_days)
        else:
            data[(t, "volume")] = rng.integers(1_000_000, 5_000_000, size=n_days).astype(float)
    cols = [(t, f) for t in tickers for f in OHLCV_FIELDS]
    df = pd.DataFrame({c: data[c] for c in cols}, index=idx)
    df.columns = pd.MultiIndex.from_tuples(cols)
    has_volume = {t: t != "^VIX" or not with_vix for t in tickers}
    return MarketDataFrame(df=df, has_volume=has_volume)


# ---------------------------------------------------------------------------
# schema tests
# ---------------------------------------------------------------------------


def test_expected_columns_include_vol_only_for_volume_bearing_tickers() -> None:
    cols = expected_feature_columns(
        tickers=["SPY", "TLT", "^VIX"],
        has_volume={"SPY": True, "TLT": True, "^VIX": False},
        horizons=[1, 5, 21],
        include_vix=True,
    )
    assert "vol_z_63d__SPY" in cols
    assert "vol_z_63d__TLT" in cols
    assert "vol_z_63d__^VIX" not in cols
    assert "level__^VIX" in cols
    assert "chg_5d__^VIX" in cols


def test_build_features_schema_matches_contract() -> None:
    mdf = _synth_mdf(["SPY", "TLT", "^VIX"])
    fs = build_features(mdf, DEFAULT_FEATURES_CFG)
    assert fs.columns == list(fs.df.columns)
    assert fs.df.notna().all().all(), "no NaN after warm-up drop"
    assert fs.df.index.is_monotonic_increasing


def test_features_dtype_is_float() -> None:
    from pandas.api.types import is_float_dtype

    mdf = _synth_mdf(["SPY", "TLT"])
    fs = build_features(mdf, DEFAULT_FEATURES_CFG)
    assert all(is_float_dtype(dt) for dt in fs.df.dtypes)


# ---------------------------------------------------------------------------
# LEAKAGE GUARD — the headline test (SPEC §2 NON-NEGOTIABLE)
# ---------------------------------------------------------------------------


def test_no_lookahead_under_future_corruption() -> None:
    """Corrupting prices after time T must not change any feature value at t ≤ T.

    This is the single hardest invariant of Phase 2. If it fails, the embedding,
    the free-energy landscape, and the backtest are all silently wrong.
    """
    tickers = ["SPY", "TLT", "^VIX"]
    mdf_clean = _synth_mdf(tickers, n_days=700, seed=1)
    fs_clean = build_features(mdf_clean, DEFAULT_FEATURES_CFG)

    # Choose a cut point well after warm-up.
    cut_pos = 500
    cut_ts = mdf_clean.df.index[cut_pos]

    # Build a "corrupted" copy where all rows AFTER cut_ts have prices replaced
    # with very different random values. If anything in the feature builder
    # reads ahead, the t ≤ cut_ts rows of fs_corrupt will diverge from fs_clean.
    rng = np.random.default_rng(999)
    df_corrupt = mdf_clean.df.copy()
    future_mask = df_corrupt.index > cut_ts
    df_corrupt.loc[future_mask, :] = (
        rng.standard_normal((future_mask.sum(), df_corrupt.shape[1])) * 50 + 1000
    )
    mdf_corrupt = MarketDataFrame(df=df_corrupt, has_volume=mdf_clean.has_volume)
    fs_corrupt = build_features(mdf_corrupt, DEFAULT_FEATURES_CFG)

    # Align on rows at or before cut_ts and compare.
    common = fs_clean.df.index.intersection(fs_corrupt.df.index)
    common_past = common[common <= cut_ts]
    assert len(common_past) > 50, "need substantial past overlap to test"
    a = fs_clean.df.loc[common_past]
    b = fs_corrupt.df.loc[common_past]
    pd.testing.assert_frame_equal(a, b, check_exact=False, atol=1e-12, rtol=0)


def test_causal_zscore_uses_only_past_values() -> None:
    """At any t, the z-score column is computed from a window strictly in the past."""
    mdf = _synth_mdf(["SPY", "TLT"], n_days=400)
    fs = build_features(mdf, DEFAULT_FEATURES_CFG)
    # We can't read internal state but we can check a derived invariant:
    # if we drop the last day from the input, the feature at every prior day stays the same.
    truncated_df = mdf.df.iloc[:-1]
    truncated = MarketDataFrame(df=truncated_df, has_volume=mdf.has_volume)
    fs_trunc = build_features(truncated, DEFAULT_FEATURES_CFG)
    common = fs.df.index.intersection(fs_trunc.df.index)
    pd.testing.assert_frame_equal(
        fs.df.loc[common], fs_trunc.df.loc[common], check_exact=False, atol=1e-12, rtol=0
    )


def test_features_index_is_subset_of_price_index() -> None:
    """Feature timestamps are a subset of the price index (no fabricated dates)."""
    mdf = _synth_mdf(["SPY", "TLT"], n_days=400)
    fs = build_features(mdf, DEFAULT_FEATURES_CFG)
    assert set(fs.df.index).issubset(set(mdf.df.index))


def test_warmup_rows_are_dropped() -> None:
    """The first 252 rows (causal_zscore_window_days) must be dropped."""
    mdf = _synth_mdf(["SPY", "TLT"], n_days=400)
    fs = build_features(mdf, DEFAULT_FEATURES_CFG)
    earliest_kept = fs.df.index[0]
    # earliest_kept must be at least window_days into the data (warm-up).
    pos = list(mdf.df.index).index(earliest_kept)
    assert pos >= DEFAULT_FEATURES_CFG.causal_zscore_window_days


def test_n_features_matches_universe_size() -> None:
    """5-asset All Weather + ^VIX → 5×3 ret + 5 vol + 4 vol_z (VIX excluded) + 1 disp + 2 vix = 27."""
    mdf = _synth_mdf(["SPY", "TLT", "GLD", "DBC", "^VIX"], n_days=600)
    fs = build_features(mdf, DEFAULT_FEATURES_CFG)
    expected = 5 * 3 + 5 + 4 + 1 + 2
    assert fs.n_features == expected, f"expected {expected} features, got {fs.n_features}"


def test_vix_volume_excluded_when_has_volume_false() -> None:
    mdf = _synth_mdf(["SPY", "^VIX"], n_days=400)
    fs = build_features(mdf, DEFAULT_FEATURES_CFG)
    assert "vol_z_63d__^VIX" not in fs.columns
    assert "vol_z_63d__SPY" in fs.columns

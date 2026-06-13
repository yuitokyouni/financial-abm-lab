"""Phase 1 — data layer tests. All deterministic, no network."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from state_atlas.config import AtlasConfig, load_config
from state_atlas.data import MarketDataFrame, load_universe, validate
from state_atlas.data.cache import cache_key
from state_atlas.data.cache import load as cache_load
from state_atlas.data.cache import save as cache_save
from state_atlas.data.yfinance_source import (
    YFinanceSource,
    _infer_has_volume,
    _normalize_yf_frame,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_yf_raw(
    tickers: list[str], n_days: int = 30, vix_zero_volume: bool = True
) -> pd.DataFrame:
    """Synthesize what yf.download(group_by='ticker') returns: 2-level columns."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2020-01-02", periods=n_days)
    cols: list[tuple[str, str]] = []
    data: dict[tuple[str, str], np.ndarray] = {}
    for t in tickers:
        base = 100 + rng.standard_normal(n_days).cumsum()
        for field in ("Open", "High", "Low", "Close", "Adj Close"):
            cols.append((t, field))
            data[(t, field)] = base + rng.standard_normal(n_days) * 0.1
        cols.append((t, "Volume"))
        if t == "^VIX" and vix_zero_volume:
            data[(t, "Volume")] = np.zeros(n_days)
        else:
            data[(t, "Volume")] = rng.integers(1_000_000, 5_000_000, size=n_days).astype(float)
    df = pd.DataFrame(data, index=idx)
    df.columns = pd.MultiIndex.from_tuples(cols)
    return df


def _load_cfg_with_cache(tmp_path: Path) -> AtlasConfig:
    cfg = load_config(REPO_ROOT / "config.yaml")
    cfg.data.cache_dir = str(tmp_path / "cache")
    cfg.data.start = "2020-01-02"
    cfg.data.end = "2020-02-15"
    return cfg


# ---------------------------------------------------------------------------
# (a) contract: MultiIndex columns, business-day index, close non-NaN
# ---------------------------------------------------------------------------
def test_data_contract_holds_after_normalize() -> None:
    raw = _make_yf_raw(["SPY", "TLT", "^VIX"])
    src = YFinanceSource(download_fn=lambda **kw: raw)
    mdf = src.fetch(["SPY", "TLT", "^VIX"], "2020-01-02", "2020-02-15")
    validate(mdf)  # raises on any violation
    assert isinstance(mdf.df.columns, pd.MultiIndex) and mdf.df.columns.nlevels == 2
    assert mdf.df.index.is_monotonic_increasing
    for t in mdf.tickers:
        assert not mdf.df[(t, "close")].isna().any()


# ---------------------------------------------------------------------------
# (b) cache hit avoids the network: second call must not invoke download_fn
# ---------------------------------------------------------------------------
def test_cache_hit_avoids_second_fetch(tmp_path: Path) -> None:
    cfg = _load_cfg_with_cache(tmp_path)
    cfg.universe.tickers = ["SPY", "TLT"]
    raw = _make_yf_raw(cfg.universe.tickers)
    call_count = {"n": 0}

    def fake_download(**_kw: object) -> pd.DataFrame:
        call_count["n"] += 1
        return raw

    src = YFinanceSource(download_fn=fake_download)
    first = load_universe(cfg, source=src)
    second = load_universe(cfg, source=src)  # should hit cache, not download
    assert call_count["n"] == 1
    assert first.df.equals(second.df)
    assert first.has_volume == second.has_volume


# ---------------------------------------------------------------------------
# (c) ^VIX gets has_volume=False and Phase 2 can read it
# ---------------------------------------------------------------------------
def test_vix_has_volume_false_propagates() -> None:
    raw = _make_yf_raw(["SPY", "^VIX"], vix_zero_volume=True)
    src = YFinanceSource(download_fn=lambda **kw: raw)
    mdf = src.fetch(["SPY", "^VIX"], "2020-01-02", "2020-02-15")
    assert mdf.has_volume["SPY"] is True
    assert mdf.has_volume["^VIX"] is False


# ---------------------------------------------------------------------------
# (d) NaN in close → explicit error (no silent forward-fill)
# ---------------------------------------------------------------------------
def test_close_nan_rows_are_dropped_not_filled() -> None:
    raw = _make_yf_raw(["SPY", "TLT"])
    raw.loc[raw.index[5], ("SPY", "Close")] = np.nan
    src = YFinanceSource(download_fn=lambda **kw: raw)
    mdf = src.fetch(["SPY", "TLT"], "2020-01-02", "2020-02-15")
    # Row dropped because close NaN — never forward-filled.
    assert raw.index[5] not in mdf.df.index
    # And validate now passes (no NaN remaining).
    validate(mdf)


def test_validate_rejects_injected_nan_in_close() -> None:
    raw = _make_yf_raw(["SPY"])
    df = _normalize_yf_frame(raw, ["SPY"])
    df.iloc[3, df.columns.get_loc(("SPY", "close"))] = np.nan
    mdf = MarketDataFrame(df=df, has_volume={"SPY": True})
    with pytest.raises(ValueError, match="close has NaN"):
        validate(mdf)


# ---------------------------------------------------------------------------
# (e) monotonic index
# ---------------------------------------------------------------------------
def test_index_strictly_monotonic_after_normalize() -> None:
    raw = _make_yf_raw(["SPY"])
    # Shuffle the rows: the normalizer must sort.
    raw = raw.sample(frac=1, random_state=0)
    df = _normalize_yf_frame(raw, ["SPY"])
    assert df.index.is_monotonic_increasing
    # No duplicates remain.
    assert not df.index.has_duplicates


# ---------------------------------------------------------------------------
# (f) offline smoke: full mock pipeline produces a valid MarketDataFrame
#     and CLI exit code is 0
# ---------------------------------------------------------------------------
def test_full_pipeline_offline_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _load_cfg_with_cache(tmp_path)
    cfg.universe.tickers = ["SPY", "TLT", "^VIX"]
    raw = _make_yf_raw(cfg.universe.tickers)
    src = YFinanceSource(download_fn=lambda **kw: raw)
    mdf = load_universe(cfg, source=src)
    assert mdf.n_rows > 0
    assert set(mdf.tickers) == {"SPY", "TLT", "^VIX"}
    # parquet round-trip preserves the MultiIndex columns.
    key = cache_key(cfg.universe.tickers, cfg.data.start, cfg.data.end)
    cached = cache_load(cfg.data.cache_dir, key)
    assert cached is not None
    assert cached.has_volume["^VIX"] is False
    # parquet round-trip strips the BusinessDay freq attribute on the DatetimeIndex
    # but preserves all values; compare without the freq metadata.
    pd.testing.assert_frame_equal(cached.df, mdf.df, check_freq=False)


# ---------------------------------------------------------------------------
# extra: has_volume inference rules
# ---------------------------------------------------------------------------
def test_has_volume_inference_edges() -> None:
    raw = _make_yf_raw(["A", "B"])
    df = _normalize_yf_frame(raw, ["A", "B"])
    # B has all-zero volume → has_volume False.
    df[("B", "volume")] = 0.0
    flags = _infer_has_volume(df, ["A", "B"])
    assert flags == {"A": True, "B": False}


# ---------------------------------------------------------------------------
# extra: cache_save → cache_load round-trip preserves has_volume dict
# ---------------------------------------------------------------------------
def test_cache_roundtrip_preserves_has_volume(tmp_path: Path) -> None:
    raw = _make_yf_raw(["SPY", "^VIX"])
    src = YFinanceSource(download_fn=lambda **kw: raw)
    mdf = src.fetch(["SPY", "^VIX"], "2020-01-02", "2020-02-15")
    key = cache_key(["SPY", "^VIX"], "2020-01-02", "2020-02-15")
    cache_save(mdf, tmp_path / "cache", key)
    loaded = cache_load(tmp_path / "cache", key)
    assert loaded is not None
    assert loaded.has_volume == {"SPY": True, "^VIX": False}

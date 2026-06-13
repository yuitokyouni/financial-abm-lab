"""Data sources. PriceSource interface in base.py; concrete sources in *_source.py.

Public entry point: ``load_universe`` — handles caching transparently.
"""

from __future__ import annotations

from state_atlas.config import AtlasConfig
from state_atlas.data import cache as _cache
from state_atlas.data.base import (
    OHLCV_FIELDS,
    MarketDataFrame,
    PriceSource,
    validate,
)
from state_atlas.data.yfinance_source import YFinanceSource

__all__ = [
    "OHLCV_FIELDS",
    "MarketDataFrame",
    "PriceSource",
    "YFinanceSource",
    "validate",
    "load_universe",
]


def load_universe(
    cfg: AtlasConfig,
    source: PriceSource | None = None,
    force_refresh: bool = False,
) -> MarketDataFrame:
    """Load OHLCV for cfg.universe, using parquet cache when possible.

    The cache key is derived from (tickers, start, end_or_today), so different
    universes never collide and rerunning with the same config on the same day
    is a no-network hit. Pass ``source=`` in tests to inject a deterministic stub.
    """
    tickers = list(cfg.universe.tickers)
    key = _cache.cache_key(tickers, cfg.data.start, cfg.data.end)
    if not force_refresh:
        cached = _cache.load(cfg.data.cache_dir, key)
        if cached is not None:
            return cached
    if source is None:
        source = YFinanceSource()
    mdf = source.fetch(tickers, cfg.data.start, cfg.data.end)
    _cache.save(mdf, cfg.data.cache_dir, key)
    return mdf

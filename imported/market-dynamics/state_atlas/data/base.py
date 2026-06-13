"""Data layer contract — single source of truth for OHLCV input.

The output of any PriceSource MUST satisfy:
- columns: MultiIndex of (ticker, field) where field in OHLCV_FIELDS
- index: tz-naive pandas.DatetimeIndex, business-day, strictly monotonic increasing
- close column never NaN inside the returned range (boundary rows are dropped, not filled)

Volume-less symbols (e.g. ^VIX) are reported via a separate `has_volume: dict[ticker, bool]`
so that Phase 2 can skip volume z-score for those tickers — we distinguish "missing data"
from "zero volume" rather than silently NaN-propagating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

OHLCV_FIELDS: tuple[str, ...] = ("open", "high", "low", "close", "adj_close", "volume")


@dataclass(frozen=True)
class MarketDataFrame:
    """Validated OHLCV frame + volume-availability flags."""

    df: pd.DataFrame
    has_volume: dict[str, bool]

    @property
    def tickers(self) -> list[str]:
        return sorted({t for t, _ in self.df.columns})

    @property
    def n_rows(self) -> int:
        return len(self.df)

    @property
    def date_range(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        return self.df.index[0], self.df.index[-1]


class PriceSource(Protocol):
    """Interface for any historical OHLCV source (yfinance, IBKR, CSV…)."""

    def fetch(
        self,
        tickers: list[str],
        start: str,
        end: str | None = None,
    ) -> MarketDataFrame: ...


def validate(mdf: MarketDataFrame) -> None:
    """Enforce the data contract. Raises ValueError on any violation.

    This is the only place where contract checks live — both the concrete sources
    and the cache loader call this so that nothing downstream sees a malformed frame.
    """
    df = mdf.df
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"index must be DatetimeIndex, got {type(df.index).__name__}")
    if df.index.tz is not None:
        raise ValueError("index must be tz-naive")
    if not df.index.is_monotonic_increasing:
        raise ValueError("index must be strictly monotonic increasing")
    if df.index.has_duplicates:
        raise ValueError("index has duplicate timestamps")
    if not isinstance(df.columns, pd.MultiIndex) or df.columns.nlevels != 2:
        raise ValueError("columns must be a 2-level MultiIndex (ticker, field)")
    fields_present = {f for _, f in df.columns}
    missing = set(OHLCV_FIELDS) - fields_present
    if missing:
        raise ValueError(f"missing OHLCV fields: {sorted(missing)}")
    tickers_in_cols = {t for t, _ in df.columns}
    if set(mdf.has_volume) != tickers_in_cols:
        raise ValueError(
            f"has_volume keys {sorted(mdf.has_volume)} do not match tickers {sorted(tickers_in_cols)}"
        )
    for t in tickers_in_cols:
        close = df[(t, "close")]
        if close.isna().any():
            raise ValueError(f"close has NaN for ticker {t} — forward-fill is forbidden")

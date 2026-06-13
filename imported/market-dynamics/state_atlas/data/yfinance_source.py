"""yfinance-backed PriceSource. Normalizes to the (ticker, field) MultiIndex contract."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from state_atlas.data.base import OHLCV_FIELDS, MarketDataFrame, validate

log = logging.getLogger(__name__)

# Map yfinance's column names to our contract.
_FIELD_RENAME = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


class YFinanceSource:
    """Fetches OHLCV via yfinance.download and reshapes to our contract.

    Volumes that are entirely 0 or NaN over the fetch window are flagged via
    has_volume=False (e.g. ^VIX). Such tickers still appear in OHLCV columns
    so the contract holds, but Phase 2 must read has_volume to know whether
    a volume z-score is meaningful.
    """

    def __init__(
        self,
        retries: int = 3,
        backoff_seconds: float = 1.5,
        download_fn: Callable[..., pd.DataFrame] | None = None,
    ) -> None:
        # download_fn is the injection point: tests pass a deterministic stub
        # instead of hitting the network.
        if download_fn is None:
            import yfinance as yf  # local import keeps yfinance optional at install time

            download_fn = yf.download
        self._download = download_fn
        self._retries = retries
        self._backoff = backoff_seconds

    def fetch(
        self,
        tickers: list[str],
        start: str,
        end: str | None = None,
    ) -> MarketDataFrame:
        if not tickers:
            raise ValueError("tickers must be non-empty")
        last_err: Exception | None = None
        for attempt in range(self._retries):
            try:
                raw = self._download(
                    tickers=tickers,
                    start=start,
                    end=end,
                    auto_adjust=False,
                    progress=False,
                    group_by="ticker",
                    threads=True,
                )
                break
            except Exception as e:  # noqa: BLE001 - retry across any transient network error
                last_err = e
                wait = self._backoff * (2**attempt)
                log.warning(
                    "yfinance fetch failed (attempt %d): %s — retrying in %.1fs",
                    attempt + 1,
                    e,
                    wait,
                )
                time.sleep(wait)
        else:
            raise RuntimeError(
                f"yfinance fetch failed after {self._retries} attempts"
            ) from last_err

        normalized = _normalize_yf_frame(raw, tickers)
        has_volume = _infer_has_volume(normalized, tickers)
        mdf = MarketDataFrame(df=normalized, has_volume=has_volume)
        validate(mdf)
        return mdf


def _normalize_yf_frame(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Reshape yfinance output into our (ticker, field) MultiIndex contract.

    yfinance returns:
      - single ticker: flat columns (Open, High, …, Volume)
      - multi-ticker: MultiIndex with group_by="ticker" → (ticker, field) outermost = ticker
    Either way we end up with (ticker_lower, field_lower) in sorted ticker order.
    """
    if isinstance(raw.columns, pd.MultiIndex):
        # group_by="ticker" produces (ticker, field). Rename field level only.
        df = raw.copy()
        df.columns = pd.MultiIndex.from_tuples(
            [(t, _FIELD_RENAME.get(f, f.lower())) for t, f in df.columns]
        )
    else:
        # Single ticker case — wrap in a (ticker, field) MultiIndex.
        ticker = tickers[0]
        df = raw.copy()
        df.columns = pd.MultiIndex.from_tuples(
            [(ticker, _FIELD_RENAME.get(c, c.lower())) for c in df.columns]
        )

    # Ensure all requested tickers and all OHLCV fields are present (fill missing with NaN columns).
    cols: list[tuple[str, str]] = []
    for t in tickers:
        for f in OHLCV_FIELDS:
            cols.append((t, f))
            if (t, f) not in df.columns:
                df[(t, f)] = float("nan")
    df = df[cols]

    df.index = pd.DatetimeIndex(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df[~df.index.duplicated(keep="first")].sort_index()

    # Drop rows where any ticker's close is NaN — we don't forward-fill.
    close_cols = [(t, "close") for t in tickers]
    df = df.dropna(subset=close_cols, how="any")
    return df


def _infer_has_volume(df: pd.DataFrame, tickers: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for t in tickers:
        col = (t, "volume")
        if col not in df.columns:
            out[t] = False
            continue
        vol = df[col]
        out[t] = bool((vol.fillna(0) > 0).any())
    return out


def _ensure_any_unused() -> Any:  # pragma: no cover - keeps typing import alive
    return None

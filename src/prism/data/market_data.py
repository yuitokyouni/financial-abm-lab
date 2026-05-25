"""Real market data fetcher via yfinance.

Fetches daily returns for calibration, replacing synthetic N(0,0.02)
pre-intervention data with actual equity returns around the NER event date.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from prism.types import MarketData


def fetch_returns(
    tickers: list[str],
    start: str,
    end: str,
    field: str = "Close",
) -> MarketData:
    """Fetch daily log-returns from Yahoo Finance.

    Args:
        tickers: List of Yahoo Finance ticker symbols.
        start: Start date (YYYY-MM-DD).
        end: End date (YYYY-MM-DD).
        field: Price field to use for return calculation.

    Returns:
        MarketData with shape (T-1, N) log-returns.

    Raises:
        ImportError: If yfinance is not installed.
        ValueError: If no data is returned for any ticker.
    """
    try:
        import yfinance as yf
    except ImportError as e:
        raise ImportError(
            "yfinance is required for real market data. Install with: pip install yfinance"
        ) from e

    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    if data.empty:
        raise ValueError(f"No data returned for {tickers} between {start} and {end}")

    if len(tickers) == 1:
        prices = data[field].values.reshape(-1, 1)
        instrument_ids = tickers
    else:
        prices = data[field].values
        instrument_ids = list(data[field].columns)

    prices = prices.astype(np.float64)
    mask = ~np.isnan(prices).any(axis=1)
    prices = prices[mask]

    if len(prices) < 2:
        raise ValueError(f"Insufficient price data (got {len(prices)} rows)")

    log_returns = np.diff(np.log(prices), axis=0)

    dates = data.index[mask].values[1:]

    return MarketData(
        returns=log_returns,
        dates=dates,
        instrument_ids=instrument_ids,
    )


def fetch_pre_intervention_data(
    ner_venue: str,
    date_effective: str,
    lookback_days: int = 504,
) -> MarketData:
    """Fetch pre-intervention data appropriate for a NER's venue and date.

    Uses venue-appropriate index ETFs as proxies.

    Args:
        ner_venue: Venue string from NER (e.g., "US_equity_smallcap").
        date_effective: Intervention effective date (YYYY-MM-DD).
        lookback_days: Calendar days before the event to fetch.

    Returns:
        MarketData with pre-intervention returns.
    """
    venue_tickers: dict[str, list[str]] = {
        "US_equity_smallcap": ["IWM"],
        "US_equity_largecap": ["SPY"],
        "EU_equity_largecap": ["EZU"],
        "JP_equity_largecap": ["EWJ"],
    }

    tickers = venue_tickers.get(ner_venue, ["SPY"])

    end_dt = datetime.strptime(date_effective, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=lookback_days)

    return fetch_returns(
        tickers=tickers,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
    )


def make_synthetic_pre_data(
    seed: int = 42,
    n_days: int = 500,
    vol: float = 0.02,
) -> MarketData:
    """Generate synthetic pre-intervention data (the Phase 1-4 default)."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, vol, (n_days, 1))
    return MarketData(returns=returns)

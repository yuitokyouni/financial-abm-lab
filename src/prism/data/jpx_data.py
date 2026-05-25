"""JPX 2014 tick size change — treatment/control data fetcher.

Fetches daily returns for TOPIX 100 (treatment) and non-TOPIX-100 (control)
stocks around the 2014-01-14 tick size reduction, using yfinance.

Treatment group: TOPIX 100 large-cap stocks affected by the tick size
reduction (min tick JPY 1 → 0.1 for stocks priced > JPY 3,000).

Control group: Mid/small-cap TSE stocks NOT in TOPIX 100 that retained
their original tick sizes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import numpy.typing as npt

JPX_EVENT_DATE = "2014-01-14"

TOPIX_100_TICKERS = [
    "7203.T",  # Toyota Motor
    "6758.T",  # Sony Group
    "9984.T",  # SoftBank Group
    "8306.T",  # MUFG
    "6501.T",  # Hitachi
    "7267.T",  # Honda Motor
    "9432.T",  # NTT
    "8058.T",  # Mitsubishi Corp
    "6902.T",  # Denso
    "4502.T",  # Takeda Pharmaceutical
    "6301.T",  # Komatsu
    "8031.T",  # Mitsui & Co
    "4503.T",  # Astellas Pharma
    "6752.T",  # Panasonic
    "7751.T",  # Canon
]

CONTROL_TICKERS = [
    "2914.T",  # Japan Tobacco (mid-cap, not in TOPIX 100 treatment)
    "9433.T",  # KDDI (was large but different tick tier)
    "4661.T",  # Oriental Land
    "6367.T",  # Daikin Industries
    "4568.T",  # Daiichi Sankyo
    "6594.T",  # Nidec
    "4063.T",  # Shin-Etsu Chemical
    "6273.T",  # SMC Corp
    "7974.T",  # Nintendo
    "9983.T",  # Fast Retailing
]

PRE_MONTHS = 6
POST_MONTHS = 6


@dataclass(frozen=True)
class JPXDataset:
    """Pre/post treatment/control returns for the JPX 2014 event."""

    treatment_pre: npt.NDArray[np.float64]
    treatment_post: npt.NDArray[np.float64]
    control_pre: npt.NDArray[np.float64]
    control_post: npt.NDArray[np.float64]
    treatment_ids: list[str]
    control_ids: list[str]
    pre_start: str
    pre_end: str
    post_start: str
    post_end: str


def _fetch_returns_matrix(
    tickers: list[str],
    start: str,
    end: str,
) -> tuple[npt.NDArray[np.float64], list[str]]:
    """Fetch daily log-returns for multiple tickers, dropping those with insufficient data."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise ImportError(
            "yfinance is required for JPX data. Install with: pip install yfinance"
        ) from e

    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError(f"No data returned for {tickers} between {start} and {end}")

    if len(tickers) == 1:
        prices = data["Close"].values.reshape(-1, 1).astype(np.float64)
        valid_tickers = tickers
    else:
        prices = data["Close"].values.astype(np.float64)
        all_cols = list(data["Close"].columns)

        nan_frac = np.isnan(prices).mean(axis=0)
        keep = nan_frac < 0.1
        prices = prices[:, keep]
        valid_tickers = [all_cols[i] for i in range(len(all_cols)) if keep[i]]

    mask = ~np.isnan(prices).any(axis=1)
    prices = prices[mask]

    if len(prices) < 30:
        raise ValueError(f"Insufficient price data after cleaning (got {len(prices)} rows)")

    log_returns = np.diff(np.log(prices), axis=0)
    return log_returns, valid_tickers


def fetch_jpx_dataset(
    treatment_tickers: list[str] | None = None,
    control_tickers: list[str] | None = None,
    pre_months: int = PRE_MONTHS,
    post_months: int = POST_MONTHS,
) -> JPXDataset:
    """Fetch the full JPX 2014 treatment/control dataset.

    Args:
        treatment_tickers: TOPIX 100 stocks (defaults to TOPIX_100_TICKERS).
        control_tickers: Non-TOPIX-100 stocks (defaults to CONTROL_TICKERS).
        pre_months: Months before event date for pre-period.
        post_months: Months after event date for post-period.

    Returns:
        JPXDataset with treatment/control × pre/post returns matrices.
    """
    if treatment_tickers is None:
        treatment_tickers = TOPIX_100_TICKERS
    if control_tickers is None:
        control_tickers = CONTROL_TICKERS

    event = datetime.strptime(JPX_EVENT_DATE, "%Y-%m-%d")
    pre_start = (event - timedelta(days=pre_months * 30)).strftime("%Y-%m-%d")
    pre_end = (event - timedelta(days=1)).strftime("%Y-%m-%d")
    post_start = JPX_EVENT_DATE
    post_end = (event + timedelta(days=post_months * 30)).strftime("%Y-%m-%d")

    treat_pre, treat_ids_pre = _fetch_returns_matrix(treatment_tickers, pre_start, pre_end)
    treat_post, treat_ids_post = _fetch_returns_matrix(treatment_tickers, post_start, post_end)
    ctrl_pre, ctrl_ids_pre = _fetch_returns_matrix(control_tickers, pre_start, pre_end)
    ctrl_post, ctrl_ids_post = _fetch_returns_matrix(control_tickers, post_start, post_end)

    treat_ids = sorted(set(treat_ids_pre) & set(treat_ids_post))
    ctrl_ids = sorted(set(ctrl_ids_pre) & set(ctrl_ids_post))

    if not treat_ids:
        raise ValueError("No treatment stocks survived both pre and post periods")
    if not ctrl_ids:
        raise ValueError("No control stocks survived both pre and post periods")

    def _select_cols(
        returns: npt.NDArray[np.float64],
        all_ids: list[str],
        keep_ids: list[str],
    ) -> npt.NDArray[np.float64]:
        idx = [all_ids.index(t) for t in keep_ids if t in all_ids]
        return returns[:, idx]

    return JPXDataset(
        treatment_pre=_select_cols(treat_pre, treat_ids_pre, treat_ids),
        treatment_post=_select_cols(treat_post, treat_ids_post, treat_ids),
        control_pre=_select_cols(ctrl_pre, ctrl_ids_pre, ctrl_ids),
        control_post=_select_cols(ctrl_post, ctrl_ids_post, ctrl_ids),
        treatment_ids=treat_ids,
        control_ids=ctrl_ids,
        pre_start=pre_start,
        pre_end=pre_end,
        post_start=post_start,
        post_end=post_end,
    )

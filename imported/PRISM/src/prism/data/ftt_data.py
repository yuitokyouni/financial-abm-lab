"""French Financial Transaction Tax (2012) — treatment/control data fetcher.

Fetches daily returns for French large-cap stocks (treatment, subject to 0.2% FTT)
and German/Dutch large-cap stocks (control, no FTT) around the 2012-08-01 event.

Treatment group: French CAC 40 large-cap stocks subject to the FTT
(market cap > EUR 1B at the time of introduction).

Control group: German DAX and Dutch AEX large-cap stocks NOT subject to the
French FTT, sharing similar European macroeconomic conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import numpy.typing as npt

FTT_EVENT_DATE = "2012-08-01"

FRENCH_TREATMENT_TICKERS = [
    "TTE.PA",  # TotalEnergies
    "SAN.PA",  # Sanofi
    "BNP.PA",  # BNP Paribas
    "AI.PA",   # Air Liquide
    "OR.PA",   # L'Oréal
    "SU.PA",   # Schneider Electric
    "CS.PA",   # AXA
    "GLE.PA",  # Société Générale
    "RI.PA",   # Pernod Ricard
    "DG.PA",   # Vinci
    "CA.PA",   # Carrefour
    "MC.PA",   # LVMH
    "ACA.PA",  # Crédit Agricole
    "BN.PA",   # Danone
    "VIV.PA",  # Vivendi
    "SGO.PA",  # Saint-Gobain
    "CAP.PA",  # Capgemini
    "ML.PA",   # Michelin
    "RNO.PA",  # Renault
    "DSY.PA",  # Dassault Systèmes
    "KER.PA",  # Kering
    "EL.PA",   # EssilorLuxottica
    "LR.PA",   # Legrand
]

EUROPEAN_CONTROL_TICKERS = [
    # German DAX stocks (no FTT in 2012)
    "SAP.DE",   # SAP
    "SIE.DE",   # Siemens
    "ALV.DE",   # Allianz
    "BAS.DE",   # BASF
    "BMW.DE",   # BMW
    "DTE.DE",   # Deutsche Telekom
    "BAYN.DE",  # Bayer
    "MUV2.DE",  # Munich Re
    "HEN3.DE",  # Henkel
    "ADS.DE",   # Adidas
    "LIN.DE",   # Linde
    "FRE.DE",   # Fresenius
    # Dutch AEX stocks (no FTT in 2012)
    "ASML.AS",  # ASML
    "PHIA.AS",  # Philips
    "INGA.AS",  # ING Group
    "KPN.AS",   # KPN
]

PRE_MONTHS = 12
POST_MONTHS = 12


@dataclass(frozen=True)
class FTTDataset:
    """Pre/post treatment/control returns for the French FTT 2012 event."""

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
            "yfinance is required for FTT data. Install with: pip install yfinance"
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


def fetch_ftt_dataset(
    treatment_tickers: list[str] | None = None,
    control_tickers: list[str] | None = None,
    pre_months: int = PRE_MONTHS,
    post_months: int = POST_MONTHS,
) -> FTTDataset:
    """Fetch the full French FTT 2012 treatment/control dataset.

    Args:
        treatment_tickers: French stocks subject to FTT (defaults to FRENCH_TREATMENT_TICKERS).
        control_tickers: European stocks not subject to FTT (defaults to EUROPEAN_CONTROL_TICKERS).
        pre_months: Months before event date for pre-period.
        post_months: Months after event date for post-period.

    Returns:
        FTTDataset with treatment/control × pre/post returns matrices.
    """
    if treatment_tickers is None:
        treatment_tickers = FRENCH_TREATMENT_TICKERS
    if control_tickers is None:
        control_tickers = EUROPEAN_CONTROL_TICKERS

    event = datetime.strptime(FTT_EVENT_DATE, "%Y-%m-%d")
    pre_start = (event - timedelta(days=pre_months * 30)).strftime("%Y-%m-%d")
    pre_end = (event - timedelta(days=1)).strftime("%Y-%m-%d")
    post_start = FTT_EVENT_DATE
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

    return FTTDataset(
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

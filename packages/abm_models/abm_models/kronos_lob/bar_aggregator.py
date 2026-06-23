"""PAMS Market から OHLCV bar 列を再構成する。

YH007-2 の課題 (Explore 調査 §6): YH006 系には execution_logs から OHLCV bar を
集約するロジックが無い。Kronos に食わせるためここで実装する。

最小設計:
  - PAMS market は `market.get_market_price(time)` で各 step の代表価格を持つ
  - bar_size = N step で集約 → 1 bar あたり (open, high, low, close, volume, amount)
  - volume は execution された数量の合計が欲しいが、PAMS の `market.get_executed_orders()` の
    API を毎 step スキャンするのは重い。最小 PoC では「板の price 列のみ」で OHLC を作り、
    volume は active 参加者数の proxy として "n_steps_with_change" を使う。Kronos 入力の
    volume 列は学習時の絶対値より相対変動に効くので、定数 1 でも動くと判断。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def build_ohlcv_from_market(
    market,
    bar_size: int,
    start_step: int = 0,
    end_step: Optional[int] = None,
    timestamp_start: str = "2026-06-01 09:00",
    timestamp_freq: str = "1min",
) -> pd.DataFrame:
    """PAMS market から OHLCV DataFrame を構成。

    Parameters
    ----------
    market : pams.market.Market
        getMarketPrice(time) で各 step の代表価格を返す。
    bar_size : int
        N step を 1 bar に集約する。
    start_step, end_step : int
        集約対象の step 範囲 [start, end)。end_step=None なら market.get_time() まで。

    Returns
    -------
    pd.DataFrame with columns ["timestamps", "open", "high", "low", "close", "volume", "amount"].
    末尾の不完全 bar (bar_size 未満) は捨てる。
    """
    if end_step is None:
        end_step = market.get_time() + 1
    n_steps = end_step - start_step
    if n_steps < bar_size:
        return pd.DataFrame(columns=["timestamps", "open", "high", "low", "close", "volume", "amount"])

    prices = np.array([market.get_market_price(t) for t in range(start_step, end_step)],
                      dtype=np.float64)
    n_bars = n_steps // bar_size
    prices = prices[: n_bars * bar_size].reshape(n_bars, bar_size)

    opens = prices[:, 0]
    highs = prices.max(axis=1)
    lows = prices.min(axis=1)
    closes = prices[:, -1]
    volumes = np.full(n_bars, float(bar_size))  # 定数 proxy. amount=vol*close
    amounts = volumes * closes
    ts = pd.date_range(timestamp_start, periods=n_bars, freq=timestamp_freq)

    return pd.DataFrame({
        "timestamps": ts, "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes, "amount": amounts,
    })


def closes_to_returns(closes: np.ndarray) -> np.ndarray:
    """log returns (NaN/0 を除去)。"""
    closes = np.asarray(closes, dtype=np.float64)
    safe = np.where(closes > 0, closes, np.nan)
    return np.diff(np.log(safe))

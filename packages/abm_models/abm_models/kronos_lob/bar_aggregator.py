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

price_source:
  - "market" (default, 後方互換): `get_market_price` = 最終約定価格。MARKET-only 構成では
    bid-ask bounce で ret_acf τ=1 ≈ -0.5 になる (Roll 1984 のアーティファクト)。
  - "mid": `get_mid_price` = (best_bid + best_ask)/2。約定の bid/ask 跨ぎから独立で、
    bounce 汚染を排除して SF を測れる。片側空で None のときは直前 mid を ffill、
    初期 None は market_price で fallback。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def _collect_prices(market, start: int, end: int, price_source: str) -> np.ndarray:
    """[start, end) の step ごとの代表価格列。`price_source` で source 切替。

    None (片側板 dry) は ffill, 先頭 None は market_price で fallback、
    それでも None なら NaN のまま (= 後段で扱う)。
    """
    if price_source == "mid":
        raw = [market.get_mid_price(t) for t in range(start, end)]
    elif price_source == "market":
        raw = [market.get_market_price(t) for t in range(start, end)]
    else:
        raise ValueError(f"price_source must be 'market' or 'mid', got {price_source!r}")

    arr = np.array([np.nan if v is None else float(v) for v in raw], dtype=np.float64)

    # forward fill
    if np.isnan(arr[0]):
        # 先頭 None: market_price で初期 fallback (PAMS は marketPrice 初期値を持つ)
        for t0 in range(start, end):
            mp = market.get_market_price(t0)
            if mp is not None:
                arr[0] = float(mp)
                break
    last = arr[0] if not np.isnan(arr[0]) else np.nan
    for i in range(arr.size):
        if np.isnan(arr[i]):
            arr[i] = last
        else:
            last = arr[i]
    return arr


def build_ohlcv_from_market(
    market,
    bar_size: int,
    start_step: int = 0,
    end_step: Optional[int] = None,
    timestamp_start: str = "2026-06-01 09:00",
    timestamp_freq: str = "1min",
    price_source: str = "market",
) -> pd.DataFrame:
    """PAMS market から OHLCV DataFrame を構成。

    Parameters
    ----------
    market : pams.market.Market
    bar_size : int
        N step を 1 bar に集約する。
    start_step, end_step : int
        集約対象の step 範囲 [start, end)。end_step=None なら market.get_time() まで。
    price_source : {"market", "mid"}
        "market" は約定価格 (bid-ask bounce 汚染あり)、"mid" は (best_bid+best_ask)/2。

    Returns
    -------
    pd.DataFrame with columns ["timestamps", "open", "high", "low", "close", "volume", "amount"].
    末尾の不完全 bar は捨てる。
    """
    if end_step is None:
        end_step = market.get_time() + 1
    n_steps = end_step - start_step
    if n_steps < bar_size:
        return pd.DataFrame(columns=["timestamps", "open", "high", "low", "close",
                                     "volume", "amount"])

    prices = _collect_prices(market, start_step, end_step, price_source)
    n_bars = n_steps // bar_size
    prices = prices[: n_bars * bar_size].reshape(n_bars, bar_size)

    opens = prices[:, 0]
    highs = prices.max(axis=1)
    lows = prices.min(axis=1)
    closes = prices[:, -1]
    volumes = np.full(n_bars, float(bar_size))  # 定数 proxy
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

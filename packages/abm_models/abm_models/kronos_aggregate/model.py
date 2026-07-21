"""YH007-1: aggregate market with shared Kronos signal and two readings.

spec 002 §4.2 / §5 を素直に最小実装した版:

  - 全 agent は **同一の** Kronos 予測 (`KronosSignal`) を共有する (§7 地雷 4 で
    レイテンシ的に正当化された "共有 1 シグナル + 異種解釈" アーキ)。
  - 読み方は 2 通り。順張り = ドリフト方向、逆張り = その符号反転 (= Kronos が
    指した方向の "過剰" を fade)。spec §4.2 のテキストは fair value 解釈で曖昧だが、
    YH007-1 の目的は「2 行動が決定論的に分岐する」ことの実証なので、最小符号反転で
    十分。多様化 (lookback / horizon / fair value 定義) は YH007-3 以降。
  - clearing は aggregate (即時): excess demand E = sum(actions), 対数リターン
    r = kappa * E / N, new_close = last_close * exp(r)。bar volume は active 数。
  - 閉ループ: clearing 後の OHLCV bar を履歴に積み足し、次 step の Kronos に食わせる
    (`SignalProvider` 経由)。Mock 信号 (テスト用) と本物の Kronos の両方を同じ抽象で
    扱えるよう、`SignalProvider` は callable とする。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Signal
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class KronosSignal:
    """Kronos の次バー予測サマリ。

    pred_close_mean / pred_close_std は sample_count 個の予測 close の標本統計量。
    confidence は |drift| / std で、参加閾値 (YH007-3) で使う。YH007-1 は使用しない。
    """
    last_close: float
    pred_close_mean: float
    pred_close_std: float

    @property
    def drift(self) -> float:
        return self.pred_close_mean - self.last_close

    @property
    def confidence(self) -> float:
        if self.pred_close_std <= 0:
            return float("inf")
        return abs(self.drift) / self.pred_close_std


class SignalProvider(Protocol):
    """OHLCV 履歴 → 次バー Kronos signal。実 Kronos でも mock でも同じシグネチャ。"""

    def __call__(self, history: pd.DataFrame) -> KronosSignal: ...


def constant_signal_provider(pred_close_mean: float, pred_close_std: float = 1.0) -> SignalProvider:
    """テスト用: 履歴によらず固定 (last_close は履歴の close 末尾を採用)。"""

    def _provider(history: pd.DataFrame) -> KronosSignal:
        return KronosSignal(
            last_close=float(history["close"].iloc[-1]),
            pred_close_mean=float(pred_close_mean),
            pred_close_std=float(pred_close_std),
        )

    return _provider


# --------------------------------------------------------------------------
# Agents (2 readings of the same signal)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TrendAgent:
    """順張り (chartist): Kronos 予測のドリフト方向に賭ける。

    action = sign(pred_close_mean - last_close) ∈ {-1, 0, +1}.
    drift==0 のとき abstain (0)。
    """
    agent_id: int

    def decide(self, signal: KronosSignal) -> int:
        d = signal.drift
        if d > 0:
            return 1
        if d < 0:
            return -1
        return 0


@dataclass(frozen=True)
class FadeAgent:
    """逆張り (contrarian): Kronos 予測が指す方向を "過剰" とみなし fade する。

    action = -sign(pred_close_mean - last_close)。YH007-1 では純粋符号反転で
    「同一信号から決定論的に逆方向の行動が出る」ことだけを示す。spec §4.2 が
    示唆する fair-value 流の精緻な定義 (price - fair_value の Z-score など)
    は YH007-3 以降に分離 (TODO)。
    """
    agent_id: int

    def decide(self, signal: KronosSignal) -> int:
        d = signal.drift
        if d > 0:
            return -1
        if d < 0:
            return 1
        return 0


# --------------------------------------------------------------------------
# Market
# --------------------------------------------------------------------------


class KronosAggregateMarket:
    """Aggregate market (即時 clearing) で Kronos shared signal × 2 reading を回す。

    Parameters
    ----------
    n_trend, n_fade : int
        各 reading の agent 数。
    kappa : float
        対数リターンへの impact 係数。r = kappa * sum(actions) / N。
    n_warmup : int
        Kronos の lookback を埋めるための bootstrap 期間。warmup の間は
        agent は trade せず, ランダム微小ノイズで価格を更新する (seed 固定)。
    n_steps : int
        warmup 後に Kronos 信号で trade するステップ数。
    initial_price : float
        bootstrap 開始時の close。
    bar_dt : str
        bar の時間単位 (pandas freq 文字列、デフォルト '1min')。
    warmup_sigma : float
        warmup 時のランダムウォーク std (log return)。
    bootstrap_start : str
        bootstrap の最初の timestamp。閉ループでも timestamp は単調増加させる。
    """

    name = "kronos_aggregate"

    def __init__(
        self,
        signal_provider: SignalProvider,
        *,
        n_trend: int = 25,
        n_fade: int = 25,
        kappa: float = 0.001,
        n_warmup: int = 128,
        n_steps: int = 200,
        initial_price: float = 100.0,
        bar_dt: str = "1min",
        warmup_sigma: float = 0.001,
        bootstrap_start: str = "2026-06-01 09:00",
    ):
        self.signal_provider = signal_provider
        self.n_trend = n_trend
        self.n_fade = n_fade
        self.kappa = float(kappa)
        self.n_warmup = int(n_warmup)
        self.n_steps = int(n_steps)
        self.initial_price = float(initial_price)
        self.bar_dt = bar_dt
        self.warmup_sigma = float(warmup_sigma)
        self.bootstrap_start = bootstrap_start
        self.trend_agents = [TrendAgent(i) for i in range(n_trend)]
        self.fade_agents = [FadeAgent(n_trend + i) for i in range(n_fade)]
        self.n_agents = n_trend + n_fade

    # ---- bootstrap a synthetic OHLCV history ------------------------------
    def _bootstrap_history(self, rng: np.random.Generator) -> pd.DataFrame:
        n = self.n_warmup
        ts = pd.date_range(self.bootstrap_start, periods=n, freq=self.bar_dt)
        rets = rng.normal(0.0, self.warmup_sigma, size=n)
        rets[0] = 0.0
        closes = self.initial_price * np.exp(np.cumsum(rets))
        opens = np.concatenate([[self.initial_price], closes[:-1]])
        highs = np.maximum(opens, closes) * (1.0 + np.abs(rng.normal(0.0, self.warmup_sigma / 2, n)))
        lows = np.minimum(opens, closes) * (1.0 - np.abs(rng.normal(0.0, self.warmup_sigma / 2, n)))
        vols = np.full(n, float(self.n_agents))
        amts = vols * closes
        return pd.DataFrame({
            "timestamps": ts, "open": opens, "high": highs, "low": lows,
            "close": closes, "volume": vols, "amount": amts,
        })

    def _next_bar(self, history: pd.DataFrame, new_close: float, actions: np.ndarray) -> dict:
        prev_close = float(history["close"].iloc[-1])
        prev_ts = pd.Timestamp(history["timestamps"].iloc[-1])
        new_ts = prev_ts + pd.tseries.frequencies.to_offset(self.bar_dt)
        high = max(prev_close, new_close)
        low = min(prev_close, new_close)
        n_active = int(np.count_nonzero(actions))
        vol = float(max(n_active, 1))
        return {
            "timestamps": new_ts,
            "open": prev_close,
            "high": high,
            "low": low,
            "close": new_close,
            "volume": vol,
            "amount": vol * new_close,
        }

    # ---- run --------------------------------------------------------------
    def run(self, *, seed: int) -> dict:
        rng = np.random.default_rng(seed)
        history = self._bootstrap_history(rng)
        prices = [float(history["close"].iloc[-1])]
        actions_log = np.zeros((self.n_steps, self.n_agents), dtype=np.int8)
        drift_log = np.zeros(self.n_steps, dtype=np.float64)
        conf_log = np.zeros(self.n_steps, dtype=np.float64)
        signal_log: list[KronosSignal] = []

        for t in range(self.n_steps):
            signal = self.signal_provider(history)
            signal_log.append(signal)
            drift_log[t] = signal.drift
            conf_log[t] = signal.confidence

            actions = np.zeros(self.n_agents, dtype=np.int8)
            for a in self.trend_agents:
                actions[a.agent_id] = a.decide(signal)
            for a in self.fade_agents:
                actions[a.agent_id] = a.decide(signal)
            actions_log[t] = actions

            excess = int(actions.sum())
            r = self.kappa * excess / self.n_agents
            new_close = float(prices[-1] * np.exp(r))
            prices.append(new_close)

            bar = self._next_bar(history, new_close, actions)
            history = pd.concat([history, pd.DataFrame([bar])], ignore_index=True)

        prices_arr = np.asarray(prices, dtype=np.float64)
        returns = np.diff(np.log(prices_arr))
        return {
            "prices": prices_arr,
            "returns": returns,
            "actions": actions_log,             # (T, N)
            "drift": drift_log,                 # (T,) signal.drift
            "confidence": conf_log,             # (T,) |drift|/std
            "history": history,                 # full OHLCV (warmup + steps)
            "n_warmup": self.n_warmup,
            "n_trend": self.n_trend,
            "n_fade": self.n_fade,
        }


# --------------------------------------------------------------------------
# Convenience type alias
# --------------------------------------------------------------------------

SignalProviderCallable = Callable[[pd.DataFrame], KronosSignal]

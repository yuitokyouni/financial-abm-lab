"""YH006: Global cognitive-history state broadcast to all SG agents.

全 SG agent が同一 step で同一 history μ(t) を見るための共有状態。
Simulator インスタンスに attribute として貼り付け、市場 ID で keying する。

量子化・shift 規則は YH005/history.py と完全一致。mid-price 差分 Δmid(t) =
P_mid(t-1) - P_mid(t-2) を C_ticks で 5 値化し、μ を base-5 で右 push。
step t の submit_orders 呼び出し時点では P_mid(t) はまだ更新中なので、
確定済みの t-1 → t-2 の差分を h(t) として使う (YH005 で t-1 step の h が
μ_t の末尾にある関係と同じラグ)。
"""

from __future__ import annotations

from typing import List


def quantize(dp: float, C: float) -> int:
    """Δp を h ∈ {-2, -1, 0, +1, +2} に量子化 (YH005/history.py と同じ)."""
    if dp > C:
        return 2
    if dp > 0:
        return 1
    if dp == 0:
        return 0
    if dp >= -C:
        return -1
    return -2


def shift_in(mu: int, h_code: int, M: int) -> int:
    """右端 push、最古を drop (base-5)."""
    return (mu * 5) % (5 ** M) + h_code


class SharedHistoryState:
    """SG 共有状態。Simulator に attach し、first-come-first-advance で更新する。

    mu: 現在の履歴 index (0..5^M-1)
    P:  累積認知価格 (Σ h(s))
    h_series: 各 step の h (debug/inspection 用)
    last_t: advance 済みの最後の step (idempotency)
    """

    def __init__(self, M: int, c_ticks: float, mu_init: int | None = None):
        self.M = M
        self.c_ticks = c_ticks
        self.K = 5 ** M
        self.mu = mu_init if mu_init is not None else self.K // 2
        self.P = 0
        self.h_series: List[int] = []
        self.last_t = -1
        # mid-price reference (for history): use last-executed price, fall back to market price.
        # Tracking cache of prices we've already seen to compute Δ.
        self._last_mid: float | None = None
        self._prev_mid: float | None = None

    def advance_to(self, market) -> None:
        """step t までの履歴を追いつかせる。同一 t で複数回呼ばれても冪等。

        mid-price proxy: market.get_market_price(t) は直近の「market price」
        (last-executed or initial price) を返す。Δ = P_mid(t-1) - P_mid(t-2)
        を h(t) に量子化する (last_t の次 step から追いつく)。
        """
        t = market.get_time()
        if t <= self.last_t:
            return

        for tt in range(self.last_t + 1, t + 1):
            if tt >= 2:
                try:
                    p_prev = market.get_market_price(tt - 1)
                    p_pprev = market.get_market_price(tt - 2)
                    dp = float(p_prev) - float(p_pprev)
                except Exception:
                    dp = 0.0
            else:
                dp = 0.0
            h = quantize(dp, self.c_ticks)
            self.P += h
            self.mu = shift_in(self.mu, h + 2, self.M)
            self.h_series.append(h)
            self.last_t = tt


def get_or_init(simulator, market, M: int, c_ticks: float) -> SharedHistoryState:
    """simulator に attach された共有状態を取得。無ければ作成。"""
    if not hasattr(simulator, "_yh006_history"):
        simulator._yh006_history = {}
    store = simulator._yh006_history
    mid = market.market_id
    if mid not in store:
        store[mid] = SharedHistoryState(M=M, c_ticks=c_ticks)
    state = store[mid]
    state.advance_to(market)
    return state

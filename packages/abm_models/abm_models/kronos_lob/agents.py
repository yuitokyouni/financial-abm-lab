"""PAMS Agent: Kronos shared signal を 2 通りに読む Trend / Fade。

YH007-1 の `TrendAgent / FadeAgent` (純 Python dataclass) を PAMS Agent に porting。
意思決定ロジック (sign(drift) vs -sign(drift)) は同じで、変わるのは:
  - 信号取得: `SharedSignalHub.get_or_update(time, history_df)` 経由
  - 履歴生成: PAMS Market から `build_ohlcv_from_market` で OHLCV 復元
  - 注文発行: MARKET_ORDER で `Order(...)` を返す
  - lookback 不足時 / signal が None なら orders=[] (warmup 中は trade しない)

設計上の注意:
  - Order の price は MARKET_ORDER でも値が必要 (PAMS 0.2.2 の Order dataclass)。
    現在の market price を仮置きする。
  - 2 agent group で同じ hub を参照させるのは Simulator 構築後に外部から
    `agent.signal_hub = hub` を inject する (`KronosLOBMarket._inject_hub` 参照)。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pams.agents import Agent
from pams.market import Market
from pams.order import MARKET_ORDER, Cancel, Order

from ..kronos_aggregate.model import KronosSignal
from .bar_aggregator import build_ohlcv_from_market
from .execution import ChildOrderScheduler
from .signal_hub import SharedSignalHub


class _KronosReaderAgent(Agent):
    """Trend/Fade 共通基盤。read_signal だけ差し替える。"""

    sign_for_positive_drift: int = +1  # Trend: +1, Fade: -1

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.order_volume: int = int(settings.get("orderVolume", 1))
        self.bar_size: int = int(settings.get("barSize", 10))
        self.lookback_bars: int = int(settings.get("lookbackBars", 32))
        # hub と timestamp config は KronosLOBMarket が後から inject する
        self.signal_hub: Optional[SharedSignalHub] = None
        self.timestamp_start: str = settings.get("timestampStart", "2026-06-01 09:00")
        self.timestamp_freq: str = settings.get("timestampFreq", "1min")
        self.action_log: list[tuple[int, int]] = []  # (time, action)
        # YH007-4 執行層: execution_horizon=1 で従来挙動 (pass-through)。
        self.execution_horizon: int = int(settings.get("executionHorizon", 1))
        self._scheduler = ChildOrderScheduler(execution_horizon=self.execution_horizon)

    def submit_orders(self, markets: List[Market]) -> List[Union[Order, Cancel]]:
        return sum((self.submit_orders_by_market(market=m) for m in markets), [])

    def _decide_action(self, signal: KronosSignal) -> int:
        d = signal.drift
        if d > 0:
            return self.sign_for_positive_drift
        if d < 0:
            return -self.sign_for_positive_drift
        return 0

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        if not self.is_market_accessible(market_id=market.market_id):
            return []
        if self.signal_hub is None:
            return []  # warmup session で hub 未注入時は no-op

        time = market.get_time()
        history = build_ohlcv_from_market(
            market, bar_size=self.bar_size, start_step=0, end_step=time + 1,
            timestamp_start=self.timestamp_start, timestamp_freq=self.timestamp_freq,
        )
        signal = self.signal_hub.get_or_update(current_step=time, history_df=history)
        # 戦略層: signal が無い (lookback 未達) なら parent=0
        action = 0 if signal is None else self._decide_action(signal)
        if signal is not None:
            self.action_log.append((time, action))

        # 執行層: parent は bar 切替時のみ発生 (= signal 更新タイミング)。
        # execution_horizon=1 で「bar あたり 1 child + 残り abstain」、
        # = bar_size で「毎 step trade」(= 従来 YH007-2/3 と等価には *ならない* が、
        # YH007-2/3 の bar 内 over-trading をやめた spec §3 準拠の挙動)。
        bar_index = time // self.bar_size
        self._scheduler.update_parent(action, bar_index=bar_index)
        child = self._scheduler.next_child()
        if child == 0:
            return []
        is_buy = child > 0
        return [Order(
            agent_id=self.agent_id, market_id=market.market_id,
            is_buy=is_buy, kind=MARKET_ORDER,
            volume=int(self.order_volume), price=None, ttl=1,
        )]


class KronosTrendAgent(_KronosReaderAgent):
    """順張り: action = sign(pred_close_mean - last_close)。"""
    sign_for_positive_drift = +1


class KronosFadeAgent(_KronosReaderAgent):
    """逆張り: action = -sign(pred_close_mean - last_close)。"""
    sign_for_positive_drift = -1

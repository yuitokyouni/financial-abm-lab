"""YH007-3: GCMG 適応型 — 戦略選択 + 参加ゲートが Kronos 信号 × 実バー payoff で内生決定される agent。

spec 002 §4.3 / §4.4 / §5 (YH007-3):
  - 各 agent は両戦略 (Trend = sign(drift), Fade = -sign(drift)) を保持
  - 直近 T 期の "実バー payoff" を rolling で記録: payoff_t = a_{t-1} * r_t ($-game)
  - 各 step で score の高い方を選択 (GCMG の argmax(scores) と同型)
  - 参加閾値 r_min を Kronos 確信度に連動: 低確信 → r_min↑ → abstain しやすい
  - Trend/Fade の比率は **外生パラメータでなく観測量** (どんな市場状況で逆張りが増えるか)

実装上の単純化 (最小実装):
  - score は per-step の (logreturn × last_action) を T-window で積算。bar 単位ではなく
    step 単位だが、bar 内で price 不変なら delta=0 で score 不変 → 結果は等価。
  - r_min = base + conf_coef / max(confidence, eps)。conf_coef=0 で静的閾値 (= 全員参加)。
  - 観測値として `action_log` に (time, chosen_action, chosen_strategy, score_trend, score_fade)
    を残し、experiment 側で「逆張り比率の時系列」を後段で再構成できるようにする。
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any, Dict, List, Union

from pams.market import Market
from pams.order import MARKET_ORDER, Cancel, Order

from .agents import _KronosReaderAgent


class KronosAdaptiveAgent(_KronosReaderAgent):
    """両戦略の rolling payoff で内生選択 + 確信度連動の参加閾値。

    Settings:
        scoreWindow (int): rolling window T (step 単位, デフォルト 50)。
        rMinBase (float): 静的 r_min ベース値 (default 0)。
        rMinConfCoef (float): 確信度連動係数 (default 0 = 静的)。
            r_min = rMinBase + rMinConfCoef / max(signal.confidence, eps)。
            confidence=inf (std=0) のときは rMinBase に縮退。
    """

    sign_for_positive_drift = +1  # base class の attribute は使わない (action_log で別 trace)

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        T = int(settings.get("scoreWindow", 50))
        self.score_window: int = T
        self.r_min_base: float = float(settings.get("rMinBase", 0.0))
        self.r_min_conf_coef: float = float(settings.get("rMinConfCoef", 0.0))
        self._payoff_buf = {
            "trend": deque([0.0] * T, maxlen=T),
            "fade": deque([0.0] * T, maxlen=T),
        }
        self._last_actions = {"trend": 0, "fade": 0}
        self._last_close: float | None = None
        # action_log overrides base: (time, chosen_action, chosen_strategy, score_trend, score_fade)
        self.action_log: list[tuple[int, int, str, float, float]] = []  # type: ignore[assignment]

    def _update_scores_from_market(self, market: Market) -> None:
        cur_close = float(market.get_market_price())
        if self._last_close is not None and self._last_close > 0 and cur_close > 0:
            r = math.log(cur_close / self._last_close)
            self._payoff_buf["trend"].append(self._last_actions["trend"] * r)
            self._payoff_buf["fade"].append(self._last_actions["fade"] * r)
        self._last_close = cur_close

    def _score(self, strat: str) -> float:
        return float(sum(self._payoff_buf[strat]))

    def _current_r_min(self, confidence: float) -> float:
        if self.r_min_conf_coef == 0.0:
            return self.r_min_base
        if math.isinf(confidence):
            return self.r_min_base
        return self.r_min_base + self.r_min_conf_coef / max(confidence, 1e-6)

    def submit_orders(self, markets: List[Market]) -> List[Union[Order, Cancel]]:
        return sum((self.submit_orders_by_market(market=m) for m in markets), [])

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        if not self.is_market_accessible(market_id=market.market_id):
            return []
        # 毎 step で前 step の (price, hypothetical action) から score 更新
        self._update_scores_from_market(market)

        chosen_a = 0
        if self.signal_hub is not None:
            from .bar_aggregator import build_ohlcv_from_market
            time = market.get_time()
            history = build_ohlcv_from_market(
                market, bar_size=self.bar_size, start_step=0, end_step=time + 1,
                timestamp_start=self.timestamp_start, timestamp_freq=self.timestamp_freq,
            )
            signal = self.signal_hub.get_or_update(current_step=time, history_df=history)
            if signal is not None:
                d = signal.drift
                trend_a = 1 if d > 0 else (-1 if d < 0 else 0)
                fade_a = -trend_a
                s_trend = self._score("trend")
                s_fade = self._score("fade")
                if s_trend >= s_fade:
                    chosen_a, chosen_strat, best_score = trend_a, "trend", s_trend
                else:
                    chosen_a, chosen_strat, best_score = fade_a, "fade", s_fade

                r_min = self._current_r_min(signal.confidence)
                if best_score <= r_min:
                    chosen_a = 0
                    chosen_strat = "abstain"

                self._last_actions["trend"] = trend_a
                self._last_actions["fade"] = fade_a
                self.action_log.append((time, chosen_a, chosen_strat, s_trend, s_fade))

        # 執行層 (YH007-4): parent → child schedule
        self._scheduler.update_parent(chosen_a)
        child = self._scheduler.next_child()
        if child == 0:
            return []
        is_buy = child > 0
        return [Order(
            agent_id=self.agent_id, market_id=market.market_id,
            is_buy=is_buy, kind=MARKET_ORDER,
            volume=int(self.order_volume), price=None, ttl=1,
        )]

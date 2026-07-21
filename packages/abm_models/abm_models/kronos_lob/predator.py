"""YH007-6: 捕食 agent (機構 4, Brunnermeier-Pedersen 2005)。

新規 LIMIT (= bid 改善 or ask 改善) を MARKET で食う agent。spec §2 機構 4 (増幅器仮説)。
シンプル化: bid 改善 (best_buy が前 step より高くなった) を売り、ask 改善 (best_sell が
前 step より低くなった) を買い、と捉える。これは厳密な "新規参入" 検出ではないが、捕食的
liquidity 消費の最小実装として spec の意図に合う。

build_lob_config の n_predator > 0 で有効化。signal_hub 不要 (板のみ見る)。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pams.agents import Agent
from pams.market import Market
from pams.order import MARKET_ORDER, Cancel, Order


class PredatorAgent(Agent):
    """価格改善 (新規 LIMIT) を MARKET で食う捕食 agent。"""

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.order_volume: int = int(settings.get("orderVolume", 1))
        self._last_best_buy: Optional[float] = None
        self._last_best_sell: Optional[float] = None
        self.predation_log: list[tuple[int, str, float]] = []  # (time, side, price)

    def submit_orders(self, markets: List[Market]) -> List[Union[Order, Cancel]]:
        return sum((self.submit_orders_by_market(m) for m in markets), [])

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        if not self.is_market_accessible(market_id=market.market_id):
            return []
        cur_buy = market.get_best_buy_price()
        cur_sell = market.get_best_sell_price()
        orders: List[Union[Order, Cancel]] = []
        time = market.get_time()

        # bid 改善 (高 bid 新規) → 食う (売り MARKET)
        if (self._last_best_buy is not None and cur_buy is not None
                and cur_buy > self._last_best_buy):
            orders.append(Order(
                agent_id=self.agent_id, market_id=market.market_id,
                is_buy=False, kind=MARKET_ORDER,
                volume=int(self.order_volume), price=None, ttl=1,
            ))
            self.predation_log.append((time, "sell_into_bid_improvement", float(cur_buy)))

        # ask 改善 (安 ask 新規) → 食う (買い MARKET)
        if (self._last_best_sell is not None and cur_sell is not None
                and cur_sell < self._last_best_sell):
            orders.append(Order(
                agent_id=self.agent_id, market_id=market.market_id,
                is_buy=True, kind=MARKET_ORDER,
                volume=int(self.order_volume), price=None, ttl=1,
            ))
            self.predation_log.append((time, "buy_into_ask_improvement", float(cur_sell)))

        # 次 step の比較用に更新
        self._last_best_buy = cur_buy
        self._last_best_sell = cur_sell
        return orders
